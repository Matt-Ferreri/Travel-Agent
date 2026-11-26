"""Demo model for offline tests, plus optional real OpenAI-compatible chat API."""
import json
import os
import urllib.request
from typing import Any

SYSTEM_PROMPT = (
    "You are a careful travel planning assistant. "
    "Follow any reusable skill procedure included in the user message. "
    "Resolve trip dates before calling weather: weekend means the upcoming Saturday–Sunday; "
    "use explicit dates when the user provides them; ask if still unclear. "
    "Pass start_date and end_date into weather_subagent. "
    "Use weather_subagent for forecasts and attractions_subagent for tourism sites. "
    "Never invent attractions, hours, ticket URLs, or weather. "
    "If a place is missing from tool results, say so. "
    "Prefer transit-friendly options when the profile says no_car. "
    "Cite source_url fields. Label fixture/sample data clearly. "
    "Refuse booking, payments, and email sends. Stay in travel-planning scope."
)


class DemoModel:
    """Deterministic scripted controller, NOT an LLM. Enables testing without credentials."""

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        from utils.dates import clarification_message, resolve_trip_dates

        raw_user = next((m.get("content", "") for m in messages if m["role"] == "user"), "")
        # Prefer the actual request text so profile wrapper words like "trip" do not trigger tools.
        if "User request:" in raw_user:
            request_text = raw_user.split("User request:", 1)[1].strip()
            # Drop any runtime-injected date resolution appendix from the parse target.
            request_text = request_text.split("\n\nResolved trip", 1)[0].strip()
            user_text = request_text.lower()
        else:
            request_text = raw_user
            user_text = raw_user.lower()
        called = {m.get("name") for m in messages if m["role"] == "tool"}

        # Out-of-scope: no tools
        if any(k in user_text for k in ["poem", "penguin", "stack trace", "debug this code"]):
            return {
                "content": (
                    "I'm a travel planning agent and can only help with destinations, "
                    "weather, places, budgets, and itineraries."
                ),
                "tool_calls": [],
            }

        # Side-effect requests: refuse without calling protected tools
        if any(k in user_text for k in ["book ", "book these", "email the", "charge my", "buy tickets"]):
            return {
                "content": (
                    "I can't book tickets, send email, or charge a card. "
                    "Those actions require explicit human approval and are blocked by the permission policy."
                ),
                "tool_calls": [],
            }

        targets: list[tuple[str, dict]] = []
        wants_plan = any(k in user_text for k in ["plan", "trip", "itinerary", "weekend", "days"])
        wants_weather = any(k in user_text for k in ["weather", "forecast", "rain", "outdoor"]) or wants_plan
        wants_places = any(
            k in user_text for k in ["place", "museum", "attraction", "restaurant", "visit", "outdoor"]
        ) or wants_plan

        city = "Boston"
        for candidate in ["boston", "cambridge", "chicago", "seattle", "new york", "nyc"]:
            if candidate in user_text:
                city = "New York" if candidate in {"new york", "nyc"} else candidate.title()
                break

        date_resolution = resolve_trip_dates(request_text)
        if wants_weather and date_resolution.status == "needs_clarification":
            return {
                "content": clarification_message(date_resolution),
                "tool_calls": [],
            }

        if wants_weather:
            weather_args: dict[str, Any] = {"city": city, "forecast_days": 3}
            if date_resolution.status == "resolved":
                weather_args["forecast_days"] = date_resolution.forecast_days_from()
                weather_args["start_date"] = date_resolution.start_date.isoformat()
                weather_args["end_date"] = date_resolution.end_date.isoformat()
            targets.append(("weather_subagent", weather_args))
        if wants_places:
            args: dict[str, Any] = {
                "city": city,
                "interests": ["museums", "outdoors", "kids"],
                "transit_friendly_only": "no_car" in user_text or "no car" in user_text,
            }
            targets.append(("attractions_subagent", args))

        pending = [(n, a) for n, a in targets if n not in called]
        if pending:
            name, args = pending[0]
            return {
                "content": None,
                "tool_calls": [
                    {
                        "id": f"demo-{name}",
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args)},
                    }
                ],
            }

        observed = [m for m in messages if m["role"] == "tool"]
        if observed:
            lines = ["This is a **demo-mode** travel briefing (scripted tool choice, not an LLM):"]
            if date_resolution.status == "resolved":
                lines.append(f"- Trip window: {date_resolution.label} ({date_resolution.source})")
            for item in observed:
                data = json.loads(item["content"])
                weather = data.get("weather") if data.get("subagent") == "weather" else data
                if data.get("subagent") == "weather" and data.get("daily"):
                    weather = data
                if isinstance(weather, dict) and weather.get("daily"):
                    days = weather["daily"].get("time", [])
                    highs = weather["daily"].get("temperature_2m_max", [])
                    lines.append(
                        f"- Weather subagent ({data.get('city', city)}, "
                        f"{weather.get('mode', data.get('mode', 'unknown'))}):"
                    )
                    for d, h in zip(days, highs):
                        lines.append(f"  - {d}: high {h}°C")
                places = data.get("places")
                if isinstance(places, list):
                    lines.append(
                        f"- Attractions subagent matched: {data.get('count', len(places))}"
                    )
                    for place in places[:5]:
                        syn = " [SYNTHETIC]" if place.get("is_synthetic") else ""
                        lines.append(
                            f"  - {place.get('name')}{syn} "
                            f"(~${place.get('estimated_cost_usd')}) "
                            f"{place.get('source_url')}"
                        )
                if data.get("conflicts"):
                    lines.append(f"- Conflicts: {'; '.join(data['conflicts'])}")
            lines.append("For Milestone 2 grading, set AGENT_MODE=openai and capture a real LLM trace.")
            return {"content": "\n".join(lines), "tool_calls": []}

        return {
            "content": (
                "Demo mode supports travel weather/places questions via subagents. "
                "Try: 'Plan a Boston weekend with museums and outdoors, no car.' "
                "For a real LLM baseline, set AGENT_MODE=openai and OPENAI_API_KEY."
            ),
            "tool_calls": [],
        }


class OpenAICompatibleModel:
    """Minimal OpenAI-compatible tool-calling client, using the Python standard library."""

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        key = os.getenv("OPENAI_API_KEY", "")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is required when AGENT_MODE=openai")
        base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        payload = {
            "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages],
            "tools": tools,
            "tool_choice": "auto",
        }
        request = urllib.request.Request(
            base + "/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                # Cloudflare (error 1010) blocks Python's default urllib User-Agent.
                "User-Agent": "TravelAgent/1.0 (+https://github.com/; urllib)",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as resp:
                result = json.loads(resp.read())
        except Exception as exc:
            raise RuntimeError(f"LLM API call failed: {exc}") from exc
        return result["choices"][0]["message"]


def get_model():
    return OpenAICompatibleModel() if os.getenv("AGENT_MODE", "demo").lower() == "openai" else DemoModel()

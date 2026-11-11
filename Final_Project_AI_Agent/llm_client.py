"""Demo model for offline tests, plus optional real OpenAI-compatible chat API."""
import json
import os
import urllib.request
from typing import Any

SYSTEM_PROMPT = (
    "You are a careful travel planning assistant. Use tools for weather and place facts. "
    "When a reusable skill procedure is included in the user message, follow it. "
    "Prefer mcp_get_weather (MCP-backed) over get_weather for forecasts. "
    "Never invent attractions, hours, ticket URLs, or weather. If a place is missing from "
    "tool results, say so. Prefer transit-friendly options when the profile says no_car. "
    "Cite source_url fields when recommending places. Label fixture/sample data clearly. "
    "Refuse booking, payments, and email sends — those require separate approval tools. "
    "Stay in travel-planning scope; decline unrelated requests."
)


class DemoModel:
    """Deterministic scripted controller, NOT an LLM. Enables testing without credentials."""

    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        raw_user = next((m.get("content", "") for m in messages if m["role"] == "user"), "")
        # Prefer the actual request text so profile wrapper words like "trip" do not trigger tools.
        if "User request:" in raw_user:
            user_text = raw_user.split("User request:", 1)[1].lower()
        else:
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
        for candidate in ["boston", "cambridge", "new york", "nyc"]:
            if candidate in user_text:
                city = "New York" if candidate in {"new york", "nyc"} else candidate.title()
                break

        if wants_weather:
            targets.append(("mcp_get_weather", {"city": city, "forecast_days": 3}))
        if wants_places:
            args: dict[str, Any] = {
                "city": city,
                "interests": ["museums", "outdoors", "kids"],
                "transit_friendly_only": "no_car" in user_text or "no car" in user_text,
            }
            targets.append(("lookup_places", args))

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
            for item in observed:
                data = json.loads(item["content"])
                if data.get("daily"):
                    days = data["daily"].get("time", [])
                    highs = data["daily"].get("temperature_2m_max", [])
                    lines.append(f"- Weather ({data.get('city', city)}, {data.get('mode', 'unknown')}):")
                    for d, h in zip(days, highs):
                        lines.append(f"  - {d}: high {h}°C")
                if "places" in data:
                    lines.append(f"- Places matched: {data.get('count', 0)}")
                    for place in data.get("places", [])[:5]:
                        syn = " [SYNTHETIC]" if place.get("is_synthetic") else ""
                        lines.append(
                            f"  - {place.get('name')}{syn} "
                            f"(~${place.get('estimated_cost_usd')}) "
                            f"{place.get('source_url')}"
                        )
            lines.append("For Milestone 2 grading, set AGENT_MODE=openai and capture a real LLM trace.")
            return {"content": "\n".join(lines), "tool_calls": []}

        return {
            "content": (
                "Demo mode supports travel weather/places questions. "
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
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
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

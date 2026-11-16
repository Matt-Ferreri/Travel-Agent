"""Transportation / weather subagent — fetches forecasts via MCP weather tool."""
from __future__ import annotations

from typing import Any

from permissions.policy import check_tool
from tools.registry import execute_tool


def run_weather_subagent(city: str, forecast_days: int = 3) -> dict[str, Any]:
    """Delegate weather research; uses mcp_get_weather (Open-Meteo via MCP)."""
    city = (city or "").strip()
    if not city:
        return {
            "subagent": "weather",
            "status": "error",
            "error": "city is required",
            "steps": [],
        }

    days = max(1, min(7, int(forecast_days or 3)))
    tool_name = "mcp_get_weather"
    decision = check_tool(tool_name)
    step: dict[str, Any] = {
        "tool": tool_name,
        "permission": decision.status,
        "input": {"city": city, "forecast_days": days},
    }
    if decision.status != "allowed":
        step["status"] = decision.status
        step["error"] = decision.reason
        return {
            "subagent": "weather",
            "status": decision.status,
            "city": city,
            "error": decision.reason,
            "steps": [step],
            "notes": "Weather subagent blocked by permission policy.",
        }

    try:
        weather = execute_tool(tool_name, {"city": city, "forecast_days": days})
        step["status"] = "ok"
        step["result_summary"] = {
            "mode": weather.get("mode"),
            "is_fixture": weather.get("is_fixture"),
            "days": (weather.get("daily") or {}).get("time"),
            "mcp": weather.get("mcp"),
        }
    except Exception as exc:  # noqa: BLE001 — return structured error to main agent
        step["status"] = "error"
        step["error"] = str(exc)
        return {
            "subagent": "weather",
            "status": "error",
            "city": city,
            "error": str(exc),
            "steps": [step],
        }

    notes = [
        "Weather subagent completed via MCP-backed Open-Meteo (or fixture fallback).",
    ]
    if weather.get("is_fixture"):
        notes.append("Result is fixture/sample weather — label clearly in the itinerary.")
    if weather.get("error"):
        notes.append(f"Tool reported: {weather.get('error')}")

    # Keep a compact shape for the LLM; full MCP payload stays under "weather".
    daily = weather.get("daily") or {}
    compact_daily = {
        "time": daily.get("time"),
        "temperature_2m_max": daily.get("temperature_2m_max"),
        "temperature_2m_min": daily.get("temperature_2m_min"),
        "precipitation_probability_max": daily.get("precipitation_probability_max"),
        "weather_code": daily.get("weather_code"),
    }
    return {
        "subagent": "weather",
        "status": "ok",
        "city": city,
        "tool_used": tool_name,
        "forecast_days": days,
        "daily": compact_daily,
        "mode": weather.get("mode"),
        "is_fixture": weather.get("is_fixture"),
        "source_url": weather.get("source_url"),
        "mcp": weather.get("mcp"),
        "steps": [step],
        "notes": " ".join(notes),
        # Full payload for traces; agent may strip before sending to the LLM.
        "weather": weather,
    }

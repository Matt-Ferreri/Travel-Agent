"""Travel tools: live/fixture weather + local places lookup."""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PLACES_FILE = DATA_DIR / "processed" / "places.json"
WEATHER_FIXTURE = DATA_DIR / "raw" / "open_meteo_boston_sample.json"

CITY_COORDS = {
    "boston": (42.3601, -71.0589),
    "cambridge": (42.3736, -71.1097),
    "new york": (40.7128, -74.0060),
    "nyc": (40.7128, -74.0060),
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "Get a short weather forecast for a city using Open-Meteo "
                "(or a saved fixture when WEATHER_MODE=fixture)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name, e.g. Boston",
                    },
                    "forecast_days": {
                        "type": "integer",
                        "description": "Number of forecast days (1-7)",
                        "minimum": 1,
                        "maximum": 7,
                    },
                },
                "required": ["city"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_places",
            "description": (
                "Look up attractions from the local places dataset. "
                "Filter by city, category, interests, or transit-friendly (no car)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City to search, e.g. Boston",
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category: museum, park, attraction, hike, walking_tour",
                    },
                    "interests": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional interest keywords, e.g. museums, outdoors, kids",
                    },
                    "transit_friendly_only": {
                        "type": "boolean",
                        "description": "If true, only return places reachable without a car",
                    },
                    "include_synthetic": {
                        "type": "boolean",
                        "description": "If true, include synthetic/fictional trap records",
                    },
                },
                "required": ["city"],
                "additionalProperties": False,
            },
        },
    },
]


def _load_places() -> list[dict[str, Any]]:
    if not PLACES_FILE.exists():
        raise FileNotFoundError(f"Places dataset missing: {PLACES_FILE}")
    data = json.loads(PLACES_FILE.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("places.json must be a JSON array")
    return data


def _normalize_city(city: str) -> str:
    return (city or "").strip().lower()


def get_weather(city: str, forecast_days: int = 3) -> dict[str, Any]:
    city_key = _normalize_city(city)
    if not city_key:
        raise ValueError("city is required")
    days = int(forecast_days or 3)
    days = max(1, min(7, days))

    mode = os.getenv("WEATHER_MODE", "fixture").lower()
    coords = CITY_COORDS.get(city_key)
    if coords is None and mode == "live":
        return {
            "error": f"Unknown city '{city}'. Supported demo cities: {sorted(CITY_COORDS)}",
            "source": "local geocoder",
        }

    if mode != "live" or coords is None:
        fixture = json.loads(WEATHER_FIXTURE.read_text(encoding="utf-8"))
        return {
            "city": city,
            "mode": "fixture",
            "source_url": fixture.get("source_url"),
            "retrieved_at": fixture.get("retrieved_at"),
            "is_fixture": True,
            "daily": fixture.get("daily"),
            "note": "Using offline weather fixture. Set WEATHER_MODE=live for Open-Meteo.",
        }

    lat, lon = coords
    query = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
            "forecast_days": days,
        }
    )
    url = f"https://api.open-meteo.com/v1/forecast?{query}"
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "TravelAgent-M2/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        fixture = json.loads(WEATHER_FIXTURE.read_text(encoding="utf-8"))
        return {
            "city": city,
            "mode": "fixture_fallback",
            "error": f"Live Open-Meteo failed: {exc}",
            "source_url": fixture.get("source_url"),
            "daily": fixture.get("daily"),
            "is_fixture": True,
        }

    return {
        "city": city,
        "mode": "live",
        "source_url": url,
        "latitude": lat,
        "longitude": lon,
        "daily": payload.get("daily"),
        "is_fixture": False,
    }


def lookup_places(
    city: str,
    category: str | None = None,
    interests: list[str] | None = None,
    transit_friendly_only: bool = False,
    include_synthetic: bool = False,
) -> dict[str, Any]:
    city_key = _normalize_city(city)
    if not city_key:
        raise ValueError("city is required")

    places = _load_places()
    interest_set = {i.strip().lower() for i in (interests or []) if i and i.strip()}
    category_key = (category or "").strip().lower() or None

    matched: list[dict[str, Any]] = []
    for place in places:
        place_city = str(place.get("city", "")).lower()
        # Treat Cambridge as Boston metro for demo searches.
        city_ok = place_city == city_key or (
            city_key == "boston" and place_city in {"boston", "cambridge"}
        )
        if not city_ok:
            continue
        if not include_synthetic and place.get("is_synthetic"):
            continue
        if category_key and str(place.get("category", "")).lower() != category_key:
            continue
        if transit_friendly_only and not place.get("transit_friendly", False):
            continue
        if interest_set:
            tags = {str(t).lower() for t in place.get("interests", [])}
            if tags.isdisjoint(interest_set):
                continue
        matched.append(place)

    return {
        "city": city,
        "count": len(matched),
        "filters": {
            "category": category_key,
            "interests": sorted(interest_set),
            "transit_friendly_only": transit_friendly_only,
            "include_synthetic": include_synthetic,
        },
        "source": str(PLACES_FILE),
        "places": matched,
        "note": "Local curated dataset. Verify hours/prices before travel.",
    }


def execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "get_weather":
        return get_weather(
            city=str(args.get("city", "")),
            forecast_days=int(args.get("forecast_days") or 3),
        )
    if name == "lookup_places":
        interests = args.get("interests") or []
        if isinstance(interests, str):
            interests = [x.strip() for x in interests.split(",") if x.strip()]
        if not isinstance(interests, list):
            raise ValueError("interests must be a list of strings")
        return lookup_places(
            city=str(args.get("city", "")),
            category=args.get("category"),
            interests=interests,
            transit_friendly_only=bool(args.get("transit_friendly_only", False)),
            include_synthetic=bool(args.get("include_synthetic", False)),
        )
    raise ValueError(f"Unknown tool: {name}")

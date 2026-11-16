"""Travel tools: live/fixture weather + OpenTripMap / local places lookup."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PLACES_FILE = DATA_DIR / "processed" / "places.json"
WEATHER_FIXTURE = DATA_DIR / "raw" / "open_meteo_boston_sample.json"

OTM_BASE = "https://api.opentripmap.com/0.1/en/places"
OTM_USER_AGENT = "TravelAgent-M2/1.0"

CITY_COORDS = {
    "boston": (42.3601, -71.0589),
    "cambridge": (42.3736, -71.1097),
    "new york": (40.7128, -74.0060),
    "nyc": (40.7128, -74.0060),
    "chicago": (41.8781, -87.6298),
}

# Map user interests / categories → OpenTripMap "kinds" (OR logic).
INTEREST_TO_KINDS: dict[str, str] = {
    "museum": "museums",
    "museums": "museums",
    "art": "museums",
    "outdoors": "gardens_and_parks,natural",
    "outdoor": "gardens_and_parks,natural",
    "parks": "gardens_and_parks",
    "park": "gardens_and_parks",
    "kids": "museums,amusement_parks,zoos,aquariums",
    "kid": "museums,amusement_parks,zoos,aquariums",
    "family": "museums,amusement_parks,zoos,aquariums",
    "hiking": "natural",
    "hike": "natural",
    "walking": "historic,architecture,gardens_and_parks",
    "history": "historic,museums",
    "science": "museums",
    "entertainment": "theatres_and_entertainments,amusement_parks",
    "attraction": "interesting_places",
    "attractions": "interesting_places",
}

CATEGORY_TO_KINDS: dict[str, str] = {
    "museum": "museums",
    "park": "gardens_and_parks",
    "attraction": "interesting_places,amusements",
    "hike": "natural",
    "walking_tour": "historic,architecture",
}

_WEATHER_PARAMS = {
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
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "mcp_get_weather",
            "description": (
                "Preferred weather tool. Calls get_weather through a real MCP stdio server "
                "(mcp_integration.weather_server), then returns the forecast. "
                "Uses Open-Meteo live or a saved fixture when WEATHER_MODE=fixture."
            ),
            "parameters": _WEATHER_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "Direct in-process weather lookup (no MCP). Prefer mcp_get_weather when available."
            ),
            "parameters": _WEATHER_PARAMS,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_places",
            "description": (
                "Look up attractions for a city. Uses OpenTripMap when PLACES_MODE=live "
                "(requires OPENTRIPMAP_API_KEY); otherwise uses the local places fixture. "
                "Filter by category, interests, or transit-friendly (no car)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City to search, e.g. Chicago or Boston",
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
                        "description": "If true, include synthetic/fictional trap records (fixture mode only)",
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


def _resolve_city_coords(city: str) -> tuple[float, float, dict[str, Any]]:
    """Return (lat, lon, meta). Uses local cache, then Open-Meteo geocoding (no key)."""
    city_key = _normalize_city(city)
    if city_key in CITY_COORDS:
        lat, lon = CITY_COORDS[city_key]
        return lat, lon, {"source": "local_cache", "query": city}

    query = urllib.parse.urlencode({"name": city.strip(), "count": 1, "language": "en", "format": "json"})
    url = f"https://geocoding-api.open-meteo.com/v1/search?{query}"
    payload = _http_get_json(url)
    results = payload.get("results") if isinstance(payload, dict) else None
    if not results:
        raise RuntimeError(f"Could not geocode city '{city}'")
    hit = results[0]
    lat = float(hit["latitude"])
    lon = float(hit["longitude"])
    return lat, lon, {
        "source": "open_meteo_geocoding",
        "source_url": url,
        "resolved_name": hit.get("name"),
        "country": hit.get("country"),
        "admin1": hit.get("admin1"),
        "query": city,
    }


def _http_get_json(url: str, timeout: int = 20) -> Any:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": OTM_USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _otm_api_key() -> str:
    return (os.getenv("OPENTRIPMAP_API_KEY") or "").strip()


def _kinds_for_query(category: str | None, interests: set[str]) -> str:
    kinds: list[str] = []
    if category:
        mapped = CATEGORY_TO_KINDS.get(category)
        if mapped:
            kinds.extend(mapped.split(","))
    for interest in interests:
        mapped = INTEREST_TO_KINDS.get(interest)
        if mapped:
            kinds.extend(mapped.split(","))
    # Deduplicate while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for kind in kinds:
        if kind not in seen:
            seen.add(kind)
            ordered.append(kind)
    return ",".join(ordered) if ordered else "museums,gardens_and_parks,interesting_places"


def _category_from_kinds(kinds: str) -> str:
    lower = (kinds or "").lower()
    if "museum" in lower:
        return "museum"
    if "park" in lower or "garden" in lower:
        return "park"
    if "natural" in lower or "view_point" in lower:
        return "hike"
    if "historic" in lower or "architecture" in lower:
        return "walking_tour"
    return "attraction"


def _interests_from_kinds(kinds: str) -> list[str]:
    lower = (kinds or "").lower()
    tags: list[str] = []
    if "museum" in lower:
        tags.append("museums")
    if any(k in lower for k in ("park", "garden", "natural", "beach")):
        tags.append("outdoors")
    if any(k in lower for k in ("zoo", "aquarium", "amusement", "child")):
        tags.append("kids")
    if "historic" in lower or "architecture" in lower:
        tags.append("history")
    return tags or ["attractions"]


def _source_url_from_detail(detail: dict[str, Any], xid: str) -> str:
    wiki = detail.get("wikipedia")
    if isinstance(wiki, str) and wiki.strip():
        return wiki.strip()
    sources = detail.get("sources") or {}
    if isinstance(sources, dict):
        for key in ("wikipedia", "wikidata", "osm"):
            val = sources.get(key)
            if isinstance(val, str) and val.startswith("http"):
                return val
    otm = detail.get("otm")
    if isinstance(otm, str) and otm.strip():
        return otm.strip()
    return f"https://opentripmap.com/en/card/{xid}"


def _normalize_otm_place(
    city: str,
    item: dict[str, Any],
    detail: dict[str, Any] | None,
) -> dict[str, Any]:
    xid = str(item.get("xid") or (detail or {}).get("xid") or "")
    kinds = str(item.get("kinds") or (detail or {}).get("kinds") or "")
    point = item.get("point") or (detail or {}).get("point") or {}
    name = (
        str(item.get("name") or "").strip()
        or str((detail or {}).get("name") or "").strip()
        or xid
    )
    hours = "unknown"
    if detail:
        opening = detail.get("opening_hours")
        if isinstance(opening, str) and opening.strip():
            hours = opening.strip()
    return {
        "id": f"otm-{xid}" if xid else f"otm-{name.lower().replace(' ', '-')[:40]}",
        "name": name,
        "city": city,
        "category": _category_from_kinds(kinds),
        "lat": point.get("lat"),
        "lon": point.get("lon"),
        "estimated_cost_usd": None,
        "hours": hours,
        "transit_friendly": True,
        "kid_friendly": "kids" in _interests_from_kinds(kinds),
        "interests": _interests_from_kinds(kinds),
        "source_url": _source_url_from_detail(detail or {}, xid),
        "retrieved_at": date.today().isoformat(),
        "is_synthetic": False,
        "otm_xid": xid,
        "otm_kinds": kinds,
        "otm_rate": item.get("rate") if item.get("rate") is not None else (detail or {}).get("rate"),
        "notes": (
            "Live OpenTripMap result. Hours/prices may be incomplete — verify before travel. "
            "transit_friendly is assumed for urban center results."
        ),
    }


def _lookup_places_live(
    city: str,
    category: str | None,
    interests: set[str],
    transit_friendly_only: bool,
    limit: int = 12,
) -> dict[str, Any]:
    api_key = _otm_api_key()
    if not api_key:
        raise RuntimeError(
            "OPENTRIPMAP_API_KEY is missing. Add it to .env and set PLACES_MODE=live."
        )

    geoname_url = (
        f"{OTM_BASE}/geoname?"
        + urllib.parse.urlencode({"name": city, "apikey": api_key})
    )
    geo = _http_get_json(geoname_url)
    if not isinstance(geo, dict) or geo.get("status") != "OK":
        raise RuntimeError(f"OpenTripMap geoname lookup failed for '{city}': {geo}")

    lat = float(geo["lat"])
    lon = float(geo["lon"])
    kinds = _kinds_for_query(category, interests)
    # Urban attractions: ~8 km radius keeps results city-centered.
    radius_m = 8000
    radius_params = {
        "radius": radius_m,
        "lon": lon,
        "lat": lat,
        "kinds": kinds,
        "rate": "2",
        "format": "json",
        "limit": max(limit * 2, 20),
        "apikey": api_key,
    }
    radius_url = f"{OTM_BASE}/radius?{urllib.parse.urlencode(radius_params)}"
    raw_list = _http_get_json(radius_url)
    if not isinstance(raw_list, list):
        raise RuntimeError(f"Unexpected OpenTripMap radius response: {raw_list}")

    # Prefer named, higher-rated places.
    candidates = [
        item
        for item in raw_list
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    candidates.sort(key=lambda x: (-int(x.get("rate") or 0), str(x.get("name"))))
    candidates = candidates[:limit]

    places: list[dict[str, Any]] = []
    detail_errors: list[str] = []
    for item in candidates:
        xid = str(item.get("xid") or "")
        detail: dict[str, Any] | None = None
        if xid:
            try:
                detail_url = (
                    f"{OTM_BASE}/xid/{urllib.parse.quote(xid)}?"
                    + urllib.parse.urlencode({"apikey": api_key})
                )
                payload = _http_get_json(detail_url)
                if isinstance(payload, dict):
                    detail = payload
            except Exception as exc:  # noqa: BLE001 — keep list usable if one detail fails
                detail_errors.append(f"{xid}: {exc}")
        place = _normalize_otm_place(city, item, detail)
        if transit_friendly_only and not place.get("transit_friendly", False):
            continue
        places.append(place)

    return {
        "city": city,
        "count": len(places),
        "filters": {
            "category": category,
            "interests": sorted(interests),
            "transit_friendly_only": transit_friendly_only,
            "include_synthetic": False,
            "kinds": kinds,
        },
        "mode": "live",
        "is_fixture": False,
        "source": "OpenTripMap",
        "source_url": radius_url.split("&apikey=")[0] + "&apikey=REDACTED",
        "geoname": {
            "name": geo.get("name"),
            "country": geo.get("country"),
            "lat": lat,
            "lon": lon,
        },
        "places": places,
        "note": (
            "Live OpenTripMap results. Ticket prices are usually unavailable from this API; "
            "verify hours and transit before travel."
            + (f" Detail fetch warnings: {len(detail_errors)}." if detail_errors else "")
        ),
    }


def get_weather(city: str, forecast_days: int = 3) -> dict[str, Any]:
    city_key = _normalize_city(city)
    if not city_key:
        raise ValueError("city is required")
    days = int(forecast_days or 3)
    days = max(1, min(7, days))

    mode = os.getenv("WEATHER_MODE", "fixture").lower()
    if mode != "live":
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

    try:
        lat, lon, geo_meta = _resolve_city_coords(city)
    except Exception as exc:
        fixture = json.loads(WEATHER_FIXTURE.read_text(encoding="utf-8"))
        return {
            "city": city,
            "mode": "fixture_fallback",
            "error": f"Geocoding failed: {exc}",
            "source_url": fixture.get("source_url"),
            "daily": fixture.get("daily"),
            "is_fixture": True,
        }

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
        "geocode": geo_meta,
        "daily": payload.get("daily"),
        "is_fixture": False,
    }


def _lookup_places_fixture(
    city: str,
    category: str | None,
    interests: set[str],
    transit_friendly_only: bool,
    include_synthetic: bool,
) -> dict[str, Any]:
    city_key = _normalize_city(city)
    places = _load_places()
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
        if category and str(place.get("category", "")).lower() != category:
            continue
        if transit_friendly_only and not place.get("transit_friendly", False):
            continue
        if interests:
            tags = {str(t).lower() for t in place.get("interests", [])}
            if tags.isdisjoint(interests):
                continue
        matched.append(place)

    available = sorted({str(p.get("city", "")).lower() for p in places if p.get("city")})
    note = "Local curated dataset (PLACES_MODE=fixture). Verify hours/prices before travel."
    if not matched:
        note += (
            f" No matches for '{city}'. Fixture cities: {available}. "
            "Set PLACES_MODE=live and OPENTRIPMAP_API_KEY for any-city OpenTripMap lookups."
        )

    return {
        "city": city,
        "count": len(matched),
        "filters": {
            "category": category,
            "interests": sorted(interests),
            "transit_friendly_only": transit_friendly_only,
            "include_synthetic": include_synthetic,
        },
        "mode": "fixture",
        "is_fixture": True,
        "source": str(PLACES_FILE),
        "places": matched,
        "note": note,
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

    interest_set = {i.strip().lower() for i in (interests or []) if i and i.strip()}
    category_key = (category or "").strip().lower() or None
    mode = os.getenv("PLACES_MODE", "fixture").lower()

    if mode == "live":
        try:
            return _lookup_places_live(
                city=city.strip(),
                category=category_key,
                interests=interest_set,
                transit_friendly_only=transit_friendly_only,
            )
        except (RuntimeError, urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError) as exc:
            fallback = _lookup_places_fixture(
                city=city,
                category=category_key,
                interests=interest_set,
                transit_friendly_only=transit_friendly_only,
                include_synthetic=include_synthetic,
            )
            fallback["mode"] = "fixture_fallback"
            fallback["error"] = f"Live OpenTripMap failed: {exc}"
            fallback["note"] = (
                f"OpenTripMap live lookup failed ({exc}). "
                + str(fallback.get("note", ""))
            )
            return fallback

    return _lookup_places_fixture(
        city=city,
        category=category_key,
        interests=interest_set,
        transit_friendly_only=transit_friendly_only,
        include_synthetic=include_synthetic,
    )


def execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "mcp_get_weather":
        from mcp_integration.client import call_mcp_weather

        return call_mcp_weather(
            city=str(args.get("city", "")),
            forecast_days=int(args.get("forecast_days") or 3),
        )
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

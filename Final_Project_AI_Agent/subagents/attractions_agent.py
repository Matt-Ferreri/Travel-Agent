"""Destination / attractions subagent — looks up tourism sites via places tool."""
from __future__ import annotations

from typing import Any

from permissions.policy import check_tool
from tools.registry import execute_tool


def run_attractions_subagent(
    city: str,
    interests: list[str] | None = None,
    category: str | None = None,
    transit_friendly_only: bool = False,
    include_synthetic: bool = False,
) -> dict[str, Any]:
    """Delegate destination research; uses lookup_places (OpenTripMap or fixture)."""
    city = (city or "").strip()
    if not city:
        return {
            "subagent": "attractions",
            "status": "error",
            "error": "city is required",
            "steps": [],
            "places": [],
            "sources": [],
        }

    interest_list = [str(i).strip() for i in (interests or []) if str(i).strip()]
    tool_name = "lookup_places"
    args = {
        "city": city,
        "interests": interest_list,
        "category": category,
        "transit_friendly_only": bool(transit_friendly_only),
        "include_synthetic": bool(include_synthetic),
    }
    decision = check_tool(tool_name)
    step: dict[str, Any] = {
        "tool": tool_name,
        "permission": decision.status,
        "input": {k: v for k, v in args.items() if v not in (None, [], "")},
    }
    if decision.status != "allowed":
        step["status"] = decision.status
        step["error"] = decision.reason
        return {
            "subagent": "attractions",
            "status": decision.status,
            "city": city,
            "error": decision.reason,
            "steps": [step],
            "places": [],
            "sources": [],
            "notes": "Attractions subagent blocked by permission policy.",
            "conflicts": [],
        }

    try:
        places_result = execute_tool(tool_name, args)
        step["status"] = "ok"
        step["result_summary"] = {
            "count": places_result.get("count"),
            "mode": places_result.get("mode"),
            "is_fixture": places_result.get("is_fixture"),
        }
    except Exception as exc:  # noqa: BLE001
        step["status"] = "error"
        step["error"] = str(exc)
        return {
            "subagent": "attractions",
            "status": "error",
            "city": city,
            "error": str(exc),
            "steps": [step],
            "places": [],
            "sources": [],
            "conflicts": [],
        }

    places = list(places_result.get("places") or [])
    sources = sorted(
        {
            str(p.get("source_url"))
            for p in places
            if p.get("source_url")
        }
    )
    conflicts: list[str] = []
    if transit_friendly_only:
        car_only = [p for p in places if not p.get("transit_friendly", False)]
        if car_only:
            conflicts.append(
                "Some matched places are not transit-friendly despite the filter; prefer listed transit options."
            )
        # Surface known car-oriented names when user asked no-car (dataset conflict helper).
        names_lower = " ".join(str(p.get("name", "")).lower() for p in places)
        if "blue hills" in names_lower:
            conflicts.append(
                "Blue Hills Reservation overlook hike is typically car-oriented; flag for no-car travelers."
            )

    notes = [
        f"Attractions subagent returned {len(places)} place(s) via {places_result.get('mode', 'unknown')} places lookup.",
    ]
    if places_result.get("note"):
        notes.append(str(places_result["note"]))
    if places_result.get("error"):
        notes.append(f"Tool reported: {places_result.get('error')}")
    if not places:
        notes.append("No matching attractions found — do not invent venues.")

    return {
        "subagent": "attractions",
        "status": "ok",
        "city": city,
        "tool_used": tool_name,
        "count": places_result.get("count", len(places)),
        "places": places,
        "sources": sources,
        "filters": places_result.get("filters"),
        "mode": places_result.get("mode"),
        "is_fixture": places_result.get("is_fixture"),
        "source": places_result.get("source"),
        "steps": [step],
        "notes": " ".join(notes),
        "conflicts": conflicts,
    }

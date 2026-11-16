"""Destination research subagent — thin wrapper over attractions_agent."""
from __future__ import annotations

from typing import Any

from subagents.attractions_agent import run_attractions_subagent


def research_subagent(
    task: str = "",
    *,
    city: str = "",
    interests: list[str] | None = None,
    transit_friendly_only: bool = False,
) -> dict[str, Any]:
    """
    Destination research entrypoint used by the main agent.

    Prefer calling via the `attractions_subagent` tool. `task` is accepted for
    compatibility and logged in notes when city is provided separately.
    """
    result = run_attractions_subagent(
        city=city or _city_from_task(task),
        interests=interests,
        transit_friendly_only=transit_friendly_only,
    )
    if task and isinstance(result, dict):
        result = dict(result)
        result["task"] = task
    return result


def _city_from_task(task: str) -> str:
    text = (task or "").lower()
    for name in ("boston", "cambridge", "chicago", "seattle", "new york", "nyc"):
        if name in text:
            return "New York" if name in {"new york", "nyc"} else name.title()
    return ""

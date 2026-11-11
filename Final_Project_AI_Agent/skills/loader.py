"""Discover and load reusable agent skills from skills/*/SKILL.md."""
from __future__ import annotations

from pathlib import Path
from typing import Any

SKILLS_DIR = Path(__file__).resolve().parent

# Keywords that mean "use the itinerary planning skill"
_ITINERARY_HINTS = (
    "plan",
    "itinerary",
    "weekend",
    "trip",
    "travel",
    "museum",
    "museums",
    "days",
    "suggest places",
    "budget",
)
_OUT_OF_SCOPE_HINTS = ("poem", "penguin", "stack trace", "debug this code")


def list_skills() -> list[str]:
    return sorted(p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md"))


def load_skill(name: str) -> dict[str, Any]:
    path = SKILLS_DIR / name / "SKILL.md"
    if not path.exists():
        raise FileNotFoundError(f"Skill not found: {name} ({path})")
    return {
        "name": name,
        "path": str(path),
        "content": path.read_text(encoding="utf-8"),
    }


def select_skill_for_prompt(prompt: str) -> dict[str, Any] | None:
    """Pick a repeatable skill when the request looks like trip planning."""
    text = (prompt or "").lower()
    if any(k in text for k in _OUT_OF_SCOPE_HINTS):
        return None
    if any(k in text for k in _ITINERARY_HINTS):
        return load_skill("itinerary_planning")
    return None

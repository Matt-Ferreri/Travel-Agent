"""Persistent synthetic trip preferences. Never store secrets or real private data in Git."""
import json
from pathlib import Path

DEFAULT_PREFS_FILE = Path(__file__).resolve().parent.parent / "data" / "processed" / "default_preferences.json"

DEFAULT_PROFILE = {
    "traveler_name": "Alex Rivera",
    "home_city": "Boston",
    "travelers": {"adults": 2, "children": 1},
    "budget_usd": 1200,
    "interests": ["museums", "outdoors", "kids"],
    "transportation": "no_car",
    "dietary": [],
    "notes": "Synthetic family profile for Milestone 2 baseline.",
    "is_synthetic": True,
}


def _default_profile() -> dict:
    if DEFAULT_PREFS_FILE.exists():
        data = json.loads(DEFAULT_PREFS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    return dict(DEFAULT_PROFILE)


def load_profile(path: str | Path) -> dict:
    file = Path(path)
    if not file.exists():
        return _default_profile()
    data = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Profile must be a JSON object")
    return data


def save_profile(path: str | Path, profile: dict) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(profile, indent=2), encoding="utf-8")


def retrieve_relevant_profile(profile: dict, task: str) -> dict:
    # Milestone 2 baseline: inject all stored preference fields (NOT selective retrieval).
    # Independent investigation (later): compare this baseline vs selective memory
    # for vague/incomplete travel requests.
    return profile

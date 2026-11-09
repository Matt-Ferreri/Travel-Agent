"""Simple persistent profile used for demo. Never store secrets or real private data in Git."""
import json
from pathlib import Path

DEFAULT_PROFILE = {"major":"Computer Science", "interests":["AI", "cybersecurity"]}

def load_profile(path: str | Path) -> dict:
    file = Path(path)
    if not file.exists():
        return dict(DEFAULT_PROFILE)
    data = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Profile must be a JSON object")
    return data

def save_profile(path: str | Path, profile: dict) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(profile, indent=2), encoding="utf-8")

def retrieve_relevant_profile(profile: dict, task: str) -> dict:
    # Starter baseline: inject all stored profile fields (NOT selective retrieval).
    # TODO (students): Implement a second memory strategy: keyword, embedding,
    # summary, or other selective retrieval. Compare against this baseline.
    return profile

"""Milestone 2 evaluation harness (demo mode by default)."""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("AGENT_MODE", "demo")
os.environ.setdefault("WEATHER_MODE", "fixture")

from agent import run_agent
from memory.store import load_profile

CASES_FILE = Path(__file__).with_name("cases_m2.json")
DEFAULT_PROFILE = Path(__file__).resolve().parent.parent / "data" / "processed" / "default_preferences.json"


def load_cases() -> list[dict]:
    return json.loads(CASES_FILE.read_text(encoding="utf-8"))


def evaluate() -> bool:
    profile = load_profile(DEFAULT_PROFILE)
    cases = load_cases()
    hits = 0
    print(f"Loaded {len(cases)} Milestone 2 cases from {CASES_FILE.name}")
    for case in cases:
        result = run_agent(case["input"], profile)
        tools = [e["tool"] for e in result["trace"] if e.get("event") == "tool_call"]
        expected = case.get("demo_expected_tool")
        if expected is None:
            ok = len(tools) == 0
        else:
            ok = expected in tools
        hits += ok
        status = "PASS" if ok else "FAIL"
        print(f"{status} {case['id']} ({case['category']}) | tools={tools} | trace_id={result.get('trace_id')}")
        print(f"  expected: {case['expected_behavior']}")
    print(f"Demo smoke score: {hits}/{len(cases)} (tool-selection checks only)")
    print("Note: For grading, also run AGENT_MODE=openai and save a real LLM+tool trace.")
    return hits == len(cases)


if __name__ == "__main__":
    raise SystemExit(0 if evaluate() else 1)

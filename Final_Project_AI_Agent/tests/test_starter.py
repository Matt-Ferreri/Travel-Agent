"""Offline smoke tests; use python -m unittest discover -s tests -v."""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("AGENT_MODE", "demo")
os.environ.setdefault("WEATHER_MODE", "fixture")

from agent import run_agent
from permissions.policy import check_tool
from memory.store import load_profile, save_profile
from tools.registry import lookup_places, get_weather


class TravelBaselineTests(unittest.TestCase):
    def test_demo_tool_loop(self):
        result = run_agent("Plan a Boston weekend with museums and outdoors, no car")
        self.assertEqual(result["stopped_reason"], "completed")
        self.assertTrue(result.get("trace_id"))
        tools = [e["tool"] for e in result["trace"] if e.get("event") == "tool_call"]
        self.assertEqual(tools, ["get_weather", "lookup_places"])
        self.assertIn("demo-mode", result["answer"].lower())

    def test_non_tool_question(self):
        tools = [e for e in run_agent("Hello")["trace"] if e.get("event") == "tool_call"]
        self.assertEqual(tools, [])

    def test_out_of_scope(self):
        result = run_agent("Write a poem about penguins")
        self.assertEqual([e for e in result["trace"] if e.get("event") == "tool_call"], [])
        self.assertIn("travel", result["answer"].lower())

    def test_step_limit(self):
        result = run_agent("Plan a Boston weekend with museums and outdoors", max_steps=1)
        self.assertEqual(result["stopped_reason"], "step_limit")

    def test_permissions(self):
        self.assertEqual(check_tool("book_tickets").status, "approval_required")
        self.assertEqual(check_tool("execute_shell").status, "denied")
        self.assertEqual(check_tool("get_weather").status, "allowed")
        self.assertEqual(check_tool("lookup_places").status, "allowed")

    def test_profile_persists(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "profile.json"
            save_profile(path, {"budget_usd": 900, "interests": ["museums"], "is_synthetic": True})
            self.assertEqual(load_profile(path)["budget_usd"], 900)

    def test_lookup_places_filters_synthetic_and_transit(self):
        result = lookup_places("Boston", interests=["outdoors"], transit_friendly_only=True)
        self.assertGreater(result["count"], 0)
        self.assertTrue(all(p.get("transit_friendly") for p in result["places"]))
        self.assertTrue(all(not p.get("is_synthetic") for p in result["places"]))

    def test_weather_fixture(self):
        weather = get_weather("Boston", forecast_days=3)
        self.assertTrue(weather.get("is_fixture"))
        self.assertIn("daily", weather)

    def test_block_unauthorized_model_tool_call(self):
        class RogueModel:
            def complete(self, messages, tools):
                if any(x["role"] == "tool" for x in messages):
                    return {"content": "Blocked as expected", "tool_calls": []}
                return {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "x",
                            "type": "function",
                            "function": {"name": "book_tickets", "arguments": "{}"},
                        }
                    ],
                }

        result = run_agent("Book these tickets now", model=RogueModel())
        tool_events = [e for e in result["trace"] if e.get("event") == "tool_call"]
        self.assertEqual(tool_events[0]["permission"], "approval_required")
        self.assertEqual(result["stopped_reason"], "completed")


if __name__ == "__main__":
    unittest.main()

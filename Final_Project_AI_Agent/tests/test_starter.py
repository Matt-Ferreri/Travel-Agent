"""Offline smoke tests; use python -m unittest discover -s tests -v."""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("AGENT_MODE", "demo")
os.environ.setdefault("WEATHER_MODE", "fixture")

from agent import run_agent, format_execution_tree
from permissions.policy import check_tool
from memory.store import load_profile, save_profile
from tools.registry import lookup_places, get_weather, execute_tool
from skills.loader import select_skill_for_prompt, list_skills
from mcp_integration.client import list_mcp_tools


class TravelBaselineTests(unittest.TestCase):
    def test_demo_tool_loop(self):
        result = run_agent("Plan a Boston weekend with museums and outdoors, no car")
        self.assertEqual(result["stopped_reason"], "completed")
        self.assertTrue(result.get("trace_id"))
        tools = [e["tool"] for e in result["trace"] if e.get("event") == "tool_call"]
        self.assertEqual(tools, ["mcp_get_weather", "lookup_places"])
        self.assertIn("demo-mode", result["answer"].lower())
        skill_events = [e for e in result["trace"] if e.get("event") == "skill_invoke"]
        self.assertEqual(len(skill_events), 1)
        self.assertEqual(skill_events[0]["skill"], "itinerary_planning")
        self.assertIn("mcp_get_weather", result["execution_tree"])
        weather = next(e for e in result["trace"] if e.get("tool") == "mcp_get_weather")
        self.assertEqual(weather["status"], "ok")
        self.assertIn("mcp", weather.get("result") or {})

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
        self.assertEqual(check_tool("mcp_get_weather").status, "allowed")
        self.assertEqual(check_tool("lookup_places").status, "allowed")

    def test_skill_loader(self):
        self.assertIn("itinerary_planning", list_skills())
        skill = select_skill_for_prompt("Plan a Boston museum weekend under budget")
        self.assertIsNotNone(skill)
        self.assertEqual(skill["name"], "itinerary_planning")
        self.assertIsNone(select_skill_for_prompt("Write a poem about penguins"))

    def test_mcp_list_and_weather(self):
        tools = list_mcp_tools()
        self.assertTrue(any(t.get("name") == "get_weather" for t in tools))
        result = execute_tool("mcp_get_weather", {"city": "Boston", "forecast_days": 3})
        self.assertTrue(result.get("is_fixture"))
        self.assertIn("mcp", result)
        self.assertIn("daily", result)

    def test_execution_tree_format(self):
        tree = format_execution_tree(
            [
                {"event": "run_start", "input_summary": "hi"},
                {"event": "skill_invoke", "skill": "itinerary_planning"},
                {"event": "tool_call", "tool": "mcp_get_weather", "status": "ok", "permission": "allowed", "result_summary": {}, "result": {"ok": True}},
                {"event": "run_end", "status": "completed", "duration_ms": 1},
            ]
        )
        self.assertIn("skill_invoke", tree)
        self.assertIn("mcp_get_weather", tree)

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

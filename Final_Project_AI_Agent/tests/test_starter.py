"""Offline smoke tests; use python -m unittest discover -s tests -v."""
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("AGENT_MODE", "demo")
os.environ.setdefault("WEATHER_MODE", "fixture")
os.environ["PLACES_MODE"] = "fixture"

from agent import run_agent, format_execution_tree
from permissions.policy import check_tool
from memory.store import load_profile, save_profile
from tools.registry import lookup_places, get_weather, execute_tool, _resolve_city_coords
from skills.loader import select_skill_for_prompt, list_skills
from mcp_integration.client import list_mcp_tools
from utils.dates import resolve_trip_dates, upcoming_weekend


class TravelBaselineTests(unittest.TestCase):
    def test_demo_tool_loop(self):
        result = run_agent("Plan a Boston weekend with museums and outdoors, no car")
        self.assertEqual(result["stopped_reason"], "completed")
        self.assertTrue(result.get("trace_id"))
        tools = [e["tool"] for e in result["trace"] if e.get("event") == "tool_call"]
        self.assertEqual(tools, ["weather_subagent", "attractions_subagent"])
        self.assertIn("demo-mode", result["answer"].lower())
        skill_events = [e for e in result["trace"] if e.get("event") == "skill_invoke"]
        self.assertEqual(len(skill_events), 1)
        self.assertEqual(skill_events[0]["skill"], "itinerary_planning")
        self.assertIn("weather_subagent", result["execution_tree"])
        date_event = next(e for e in result["trace"] if e.get("event") == "date_resolve")
        self.assertEqual(date_event["status"], "resolved")
        self.assertEqual(date_event["output_summary"]["source"], "weekend")
        sat, sun = upcoming_weekend()
        self.assertEqual(date_event["output_summary"]["trip_dates"], [sat.isoformat(), sun.isoformat()])
        weather = next(
            e
            for e in result["trace"]
            if e.get("event") == "tool_call" and e.get("tool") == "weather_subagent"
        )
        self.assertEqual(weather["status"], "ok")
        self.assertEqual(weather.get("input_summary", {}).get("start_date"), sat.isoformat())
        self.assertEqual(weather.get("input_summary", {}).get("end_date"), sun.isoformat())
        # Gate must appear before the matching tool_call in the trace.
        weather_perm_idx = next(
            i
            for i, e in enumerate(result["trace"])
            if e.get("event") == "permission_decision" and e.get("tool") == "weather_subagent"
        )
        weather_call_idx = next(
            i
            for i, e in enumerate(result["trace"])
            if e.get("event") == "tool_call" and e.get("tool") == "weather_subagent"
        )
        self.assertLess(weather_perm_idx, weather_call_idx)
        weather_result = weather.get("result") or {}
        self.assertEqual(weather_result.get("subagent"), "weather")
        self.assertIn("mcp", (weather_result.get("weather") or {}))
        self.assertEqual((weather_result.get("daily") or {}).get("time"), [sat.isoformat(), sun.isoformat()])

    def test_resolve_weekend_and_explicit_dates(self):
        wednesday = date(2026, 11, 25)
        weekend = resolve_trip_dates("Plan a Boston weekend", today=wednesday)
        self.assertEqual(weekend.status, "resolved")
        self.assertEqual(weekend.source, "weekend")
        self.assertEqual(weekend.start_date, date(2026, 11, 28))
        self.assertEqual(weekend.end_date, date(2026, 11, 29))

        explicit = resolve_trip_dates(
            "Plan Boston for 2026-11-26 to 2026-11-27 with museums",
            today=wednesday,
        )
        self.assertEqual(explicit.status, "resolved")
        self.assertEqual(explicit.source, "explicit")
        self.assertEqual(explicit.trip_dates, ["2026-11-26", "2026-11-27"])

        # Explicit dates win over the weekend keyword.
        mixed = resolve_trip_dates(
            "Weekend ideas for Boston on 2026-11-26 to 2026-11-27",
            today=wednesday,
        )
        self.assertEqual(mixed.source, "explicit")
        self.assertEqual(mixed.start_date, date(2026, 11, 26))

        unclear = resolve_trip_dates("Plan a Boston trip with museums", today=wednesday)
        self.assertEqual(unclear.status, "needs_clarification")

    def test_resolve_relative_dates(self):
        wednesday = date(2026, 11, 25)
        tomorrow = resolve_trip_dates("What's the weather in Boston tomorrow?", today=wednesday)
        self.assertEqual(tomorrow.status, "resolved")
        self.assertEqual(tomorrow.source, "relative")
        self.assertEqual(tomorrow.start_date, date(2026, 11, 26))
        self.assertEqual(tomorrow.end_date, date(2026, 11, 26))

        in_two = resolve_trip_dates("Plan Boston in 2 days", today=wednesday)
        self.assertEqual(in_two.source, "relative")
        self.assertEqual(in_two.start_date, date(2026, 11, 27))

        from_now = resolve_trip_dates("Boston museums 2 days from now", today=wednesday)
        self.assertEqual(from_now.start_date, date(2026, 11, 27))

        next_three = resolve_trip_dates("Plan the next 3 days in Boston", today=wednesday)
        self.assertEqual(next_three.trip_dates, ["2026-11-25", "2026-11-26", "2026-11-27"])

        next_friday = resolve_trip_dates("Boston next Friday", today=wednesday)
        self.assertEqual(next_friday.start_date, date(2026, 11, 27))

        # Explicit dates still beat relative phrasing.
        mixed = resolve_trip_dates(
            "Tomorrow in Boston on 2026-11-28 to 2026-11-29",
            today=wednesday,
        )
        self.assertEqual(mixed.source, "explicit")
        self.assertEqual(mixed.start_date, date(2026, 11, 28))

    def test_ask_before_weather_when_dates_missing(self):
        result = run_agent("Plan a Boston trip with museums and outdoors, no car")
        self.assertEqual(result["stopped_reason"], "needs_clarification")
        self.assertEqual([e for e in result["trace"] if e.get("event") == "tool_call"], [])
        self.assertIn("dates", result["answer"].lower())

    def test_explicit_dates_passed_to_weather(self):
        start = date.today() + timedelta(days=1)
        end = start + timedelta(days=1)
        prompt = f"Plan Boston museums {start.isoformat()} to {end.isoformat()}"
        result = run_agent(prompt)
        self.assertEqual(result["stopped_reason"], "completed")
        weather = next(
            e
            for e in result["trace"]
            if e.get("event") == "tool_call" and e.get("tool") == "weather_subagent"
        )
        self.assertEqual(weather["input_summary"]["start_date"], start.isoformat())
        self.assertEqual(weather["input_summary"]["end_date"], end.isoformat())
        self.assertEqual((weather["result"].get("daily") or {}).get("time"), [start.isoformat(), end.isoformat()])

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
        self.assertEqual(check_tool("weather_subagent").status, "allowed")
        self.assertEqual(check_tool("attractions_subagent").status, "allowed")

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
        self.assertTrue(result.get("is_fixture"))
        self.assertEqual(result.get("mode"), "fixture")
        self.assertTrue(all(p.get("transit_friendly") for p in result["places"]))
        self.assertTrue(all(not p.get("is_synthetic") for p in result["places"]))

    def test_lookup_places_unknown_city_fixture_is_empty(self):
        result = lookup_places("Chicago", interests=["museums"])
        self.assertEqual(result["count"], 0)
        self.assertEqual(result.get("mode"), "fixture")
        self.assertIn("PLACES_MODE=live", result.get("note", ""))

    def test_weather_fixture(self):
        weather = get_weather("Boston", forecast_days=3)
        self.assertTrue(weather.get("is_fixture"))
        self.assertIn("daily", weather)

    def test_resolve_city_coords_local_cache(self):
        lat, lon, meta = _resolve_city_coords("Boston")
        self.assertAlmostEqual(lat, 42.3601, places=3)
        self.assertAlmostEqual(lon, -71.0589, places=3)
        self.assertEqual(meta.get("source"), "local_cache")

    def test_weather_and_attractions_subagents(self):
        weather = execute_tool("weather_subagent", {"city": "Boston", "forecast_days": 3})
        self.assertEqual(weather.get("subagent"), "weather")
        self.assertEqual(weather.get("status"), "ok")
        self.assertTrue((weather.get("weather") or {}).get("is_fixture"))
        self.assertEqual(weather["steps"][0]["tool"], "mcp_get_weather")

        places = execute_tool(
            "attractions_subagent",
            {"city": "Boston", "interests": ["outdoors"], "transit_friendly_only": True},
        )
        self.assertEqual(places.get("subagent"), "attractions")
        self.assertEqual(places.get("status"), "ok")
        self.assertGreater(places.get("count", 0), 0)
        self.assertEqual(places["steps"][0]["tool"], "lookup_places")

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

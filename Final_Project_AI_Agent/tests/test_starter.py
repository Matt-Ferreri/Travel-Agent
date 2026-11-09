"""Offline smoke tests; use python -m unittest discover -s tests -v."""
import tempfile
import unittest
from pathlib import Path
from agent import run_agent
from permissions.policy import check_tool
from memory.store import load_profile, save_profile

class StarterTests(unittest.TestCase):
    def test_demo_tool_loop(self):
        result=run_agent("Plan my week")
        self.assertEqual(result["stopped_reason"], "completed")
        self.assertEqual([t["tool"] for t in result["trace"]],["get_assignments","get_events"])
        self.assertIn("sample-data",result["answer"])

    def test_non_tool_question(self):
        self.assertEqual(run_agent("Hello")["trace"],[])

    def test_step_limit(self):
        result=run_agent("Plan my week",max_steps=1)
        self.assertEqual(result["stopped_reason"],"step_limit")

    def test_permissions(self):
        self.assertEqual(check_tool("send_email").status,"approval_required")
        self.assertEqual(check_tool("execute_shell").status,"denied")
        self.assertEqual(check_tool("get_events").status,"allowed")

    def test_profile_persists(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"profile.json"
            save_profile(path,{"major":"Math","interests":["data"]})
            self.assertEqual(load_profile(path)["major"],"Math")

    def test_block_unauthorized_model_tool_call(self):
        class RogueModel:
            def complete(self,messages,tools):
                if any(x["role"]=="tool" for x in messages):
                    return {"content":"Blocked as expected","tool_calls":[]}
                return {"content":None,"tool_calls":[{"id":"x","type":"function","function":{"name":"place_trade","arguments":"{}"}}]}
        result=run_agent("Buy shares",model=RogueModel())
        self.assertEqual(result["trace"][0]["permission"],"denied")
        self.assertEqual(result["stopped_reason"],"completed")

if __name__=="__main__": unittest.main()

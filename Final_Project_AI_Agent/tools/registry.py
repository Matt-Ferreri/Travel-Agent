"""Two safe local demo tools; replace or extend for your project."""
from datetime import datetime
from typing import Any

TOOL_SCHEMAS = [
    {"type":"function","function":{"name":"get_assignments","description":"List assignments in the sample course dataset.","parameters":{"type":"object","properties":{},"additionalProperties":False}}},
    {"type":"function","function":{"name":"get_events","description":"List upcoming sample calendar events.","parameters":{"type":"object","properties":{},"additionalProperties":False}}},
]
SAMPLE_ASSIGNMENTS = [
    {"course":"Algorithms","task":"Problem set on dynamic programming","due":"Friday","priority":"high"},
    {"course":"GenAI","task":"Review agent architecture","due":"Thursday","priority":"medium"},
]
SAMPLE_EVENTS = [{"title":"Career workshop","when":"Wednesday 4 PM"}, {"title":"Study group","when":"Tuesday 3 PM"}]

def execute_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    # TODO (students): Replace sample data with a real, authorized source.
    # TODO (students): Add at least one additional meaningful tool and update its schema.
    if name == "get_assignments":
        return {"source":"sample dataset (not live)","assignments":SAMPLE_ASSIGNMENTS}
    if name == "get_events":
        return {"source":"sample dataset (not live)","events":SAMPLE_EVENTS}
    raise ValueError(f"Unknown tool: {name}")

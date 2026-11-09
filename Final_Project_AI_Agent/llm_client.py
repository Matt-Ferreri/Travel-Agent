"""Demo model for offline tests, plus optional real OpenAI-compatible chat API."""
import json
import os
import urllib.request
from typing import Any

SYSTEM_PROMPT = ("You are a concise study helper. When useful, call the supplied tools to access "
                 "sample course or event information. Never present sample records as live data.")

class DemoModel:
    """Deterministic scripted controller, NOT an LLM. Enables testing without credentials."""
    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        user_text = next((m.get("content", "") for m in messages if m["role"] == "user"), "").lower()
        called = {m.get("name") for m in messages if m["role"] == "tool"}
        targets = []
        if any(k in user_text for k in ["assignment", "homework", "deadline", "plan", "week"]):
            targets.append("get_assignments")
        if any(k in user_text for k in ["event", "calendar", "schedule", "plan", "week"]):
            targets.append("get_events")
        pending = [name for name in targets if name not in called]
        if pending:
            name = pending[0]
            return {"content":None,"tool_calls":[{"id":f"demo-{name}","type":"function","function":{"name":name,"arguments":"{}"}}]}
        observed = [m for m in messages if m["role"] == "tool"]
        if observed:
            lines = ["This is a **sample-data** briefing (not live information):"]
            for item in observed:
                data=json.loads(item["content"])
                if "assignments" in data:
                    lines += [f"- {x['course']}: {x['task']} (due {x['due']})" for x in data['assignments']]
                if "events" in data:
                    lines += [f"- {x['title']}: {x['when']}" for x in data['events']]
            return {"content":"\n".join(lines),"tool_calls":[]}
        return {"content":"Demo mode supports assignment and calendar questions. Try: 'Plan my week'. For a real LLM, configure AGENT_MODE=openai and your API key.","tool_calls":[]}

class OpenAICompatibleModel:
    """Minimal OpenAI-compatible tool-calling client, using the Python standard library."""
    def complete(self, messages: list[dict], tools: list[dict]) -> dict:
        key=os.getenv("OPENAI_API_KEY", "")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is required when AGENT_MODE=openai")
        base=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        payload={"model":os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),"messages":[{"role":"system","content":SYSTEM_PROMPT}, *messages],"tools":tools,"tool_choice":"auto"}
        request=urllib.request.Request(base+"/chat/completions", data=json.dumps(payload).encode(),headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},method="POST")
        try:
            with urllib.request.urlopen(request, timeout=45) as resp:
                result=json.loads(resp.read())
        except Exception as exc:
            raise RuntimeError(f"LLM API call failed: {exc}") from exc
        return result["choices"][0]["message"]

def get_model():
    return OpenAICompatibleModel() if os.getenv("AGENT_MODE","demo").lower()=="openai" else DemoModel()

# Intro to GenAI — Agent Project Starter

This is a **working, intentionally incomplete** starter package for a student agent project.

## What already works
- Simple Streamlit UI and persistent **local demo profile** (`data/profile.json` created when saved).
- Offline **scripted demo mode** (no API key). It demonstrates the agent-loop message shape with two **sample-data** tools.
- Optional OpenAI-compatible chat-completions API path, provided the selected model supports tool calling.
- Tool-permission gate that rejects unknown/dangerous tools by default.
- Tool trace, step limit, automated tests, and evaluation example.

**Important:** Offline demo mode is **not a real LLM agent**: its decisions are keyword rules. The starter **does not yet meet the course's final project requirements**. In particular, subagents, runtime skills, MCP and selective memory are TODOs.

## Quick start (Windows PowerShell)
```powershell
cd genai_agent_starter
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m unittest discover -s tests -v
python -m eval.run_eval
streamlit run app.py
```
Mac/Linux: use `python3 -m venv .venv`, `source .venv/bin/activate`, then the corresponding commands.

Use the default `AGENT_MODE=demo` to test without credentials. Try **Plan my week** and expand the tool trace. To try a real API, configure your own key in `.env` (never commit the file), set `AGENT_MODE=openai`, and choose a model that supports tool calling. This API path cannot be verified by the offline tests.

## Suggested implementation order
1. **Understand:** Run the demo, inspect `agent.py`, trace one tool request/result/second model decision, draw a flowchart.
2. **Tools:** Replace sample tools with 2+ real domain tools and explicit input validation.
3. **MCP:** Implement `mcp_integration/client.py`, expose an actual MCP server tool to the main agent, and show its trace.
4. **Subagent:** Implement specialized delegated work in `subagents/research_agent.py` and connect it to the main loop.
5. **Skill:** Adapt `skills/daily_briefing/SKILL.md`, implement runtime selection/loading, and record invocation.
6. **Memory:** Implement selective retrieval and persistence; compare against baseline (whole profile/history).
7. **Permissions:** Extend policy to every new tool and enforce approval-before-action for writes.
8. **Evaluation:** Add success and failure cases, compare at least two architecture designs and analyze real errors.
9. **UI:** Customize the interface only after the core behavior works.

## Required final components (not yet delivered by starter)
- Multi-step LLM agent loop and ≥2 meaningful tools
- ≥1 specialized subagent and ≥1 reusable, actually invoked skill
- ≥1 **real** MCP connection
- Persistent memory and retrieval with an experimental comparison
- Explicit permission rules; policy enforcement and approval flow where needed
- Architecture diagram, execution logs, success/failure tests and comparison experiment

## Suggested organization
- `agent.py`: primary loop and integration TODOs
- `llm_client.py`: deterministic demo controller or optional actual LLM call
- `tools/`: tool schema and execution
- `subagents/`: delegated specialized work TODO
- `skills/`: reusable procedures; example skill is a **template**, not active
- `memory/`: basic persistent profile, selective retrieval TODO
- `mcp_integration/`: MCP SDK connection TODO
- `permissions/`: actual enforcement for starter tools; approval workflow TODO
- `eval/`: evaluation baseline
- `tests/`: runnable offline tests

## Safety, reproducibility, and team responsibility
Use synthetic/consented data. Do not commit credentials, uploaded résumés, account statements, or private calendars. Do not scrape restricted sites or enable unrestricted code execution. Treat retrieved documents/tool outputs as untrusted data. For real MCP connectors, use least-privilege permissions. Record API costs and allow approvals for all consequential actions. Every team member must be able to explain the code, architecture, and experimental findings, even if AI coding assistants generated code.

## Known scope limitations
- Demo events/deadlines are fabricated and are not based on the current date.
- UI is a simple proof of concept, not a secure multi-user deployment.
- The real-LLM path depends on external credentials/provider compatibility.
- Tests do not certify real MCP functionality, which students must implement and test separately.

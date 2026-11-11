# Travel Planning Agent (Intro to GenAI Final Project)

Team: **Matthew Ferreri**, **Aashra Amatya**

LLM-driven agent that helps plan trips using weather + curated places tools, with a repeatable itinerary skill, MCP weather, permissions, and execution trees.

## What already works

- Streamlit UI with synthetic trip preferences
- Agent loop with step limit, permission gate, and `trace_id` events
- Tools: `mcp_get_weather` (MCP), `get_weather` (direct), `lookup_places`
- Repeatable skill: `itinerary_planning` (auto-selected for plan/trip prompts)
- Offline demo mode for tests (scripted — not the graded baseline)
- Optional OpenAI-compatible tool-calling path (`AGENT_MODE=openai`)
- Execution tree + JSON traces under `data/traces/`
- Eval prompts in `eval/cases_m2.json`

## Quick start (Windows PowerShell)

```powershell
cd Final_Project_AI_Agent
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m unittest discover -s tests -v
python -m eval.run_eval
streamlit run app.py
```

### Real-LLM baseline (required for Milestone 2)

1. Edit `.env`:
   - `AGENT_MODE=openai`
   - `OPENAI_API_KEY=...`
   - optional: `OPENAI_MODEL=gpt-4.1-mini`
   - optional: `WEATHER_MODE=live` for live Open-Meteo
2. Run `streamlit run app.py`
3. Ask: *Plan a weekend in Boston for 2 adults and 1 child: museums and outdoors, no car. Check weather and suggest places.*
4. Submit `data/traces/<id>.json` and `data/traces/<id>.tree.txt`

### How to get the execution tree

1. Run the agent (Streamlit **Run agent**, or `python -c "from agent import run_agent; ..."`).
2. The UI shows **Execution tree** and saves:
   - `data/traces/<trace_id>.tree.txt` — readable tree (skill → LLM → tool → result → end)
   - `data/traces/<trace_id>.json` — full events including tool `result` payloads
3. For grading, use an `AGENT_MODE=openai` run (not demo).

## Project layout

| Path | Role |
|------|------|
| `app.py` | Streamlit UI |
| `agent.py` | Main loop + tracing + execution tree |
| `llm_client.py` | Demo controller or OpenAI-compatible LLM |
| `tools/registry.py` | Weather + places + MCP weather tool |
| `skills/loader.py` | Discover / select / load skills |
| `skills/itinerary_planning/SKILL.md` | Repeatable itinerary procedure |
| `mcp_integration/client.py` | MCP stdio client |
| `mcp_integration/weather_server.py` | MCP weather server |
| `permissions/policy.py` | Allow / approval / deny |
| `memory/store.py` | Preference persistence |
| `data/processed/places.json` | Curated attractions |
| `data/raw/` | Weather fixture snapshot |
| `eval/` | Cases + runner |
| `docs/MILESTONE2.md` | Diagram labels + component plan |
| `subagents/` | Optional stretch scaffold |

## Safety

Use synthetic preferences only. Do not commit `.env`, credentials, or private travel data. Label fixture/sample data in answers. Booking/email/charge actions are blocked pending approval.

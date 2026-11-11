# Travel Planning Agent (Intro to GenAI Final Project)

Team: **Matthew Ferreri**, **Aashra Amatya**

LLM-driven agent that helps plan trips using weather + curated places tools, with permissions and execution traces. Milestone 2 delivers a **real-LLM tool-calling baseline**; subagent, skill runtime, MCP, and selective memory are planned next.

## What already works

- Streamlit UI with synthetic trip preferences
- Agent loop with step limit, permission gate, and `trace_id` events
- Tools: `get_weather` (Open-Meteo live or fixture), `lookup_places` (local dataset)
- Offline demo mode for tests (scripted — not the graded baseline)
- Optional OpenAI-compatible tool-calling path (`AGENT_MODE=openai`)
- Milestone 2 eval prompts in `eval/cases_m2.json`

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
4. Save/share the JSON written under `data/traces/`

## Project layout

| Path | Role |
|------|------|
| `app.py` | Streamlit UI |
| `agent.py` | Main loop + tracing |
| `llm_client.py` | Demo controller or OpenAI-compatible LLM |
| `tools/registry.py` | Weather + places tools |
| `permissions/policy.py` | Allow / approval / deny |
| `memory/store.py` | Preference persistence |
| `data/processed/places.json` | Curated attractions |
| `data/raw/` | Weather fixture snapshot |
| `eval/` | M2 cases + runner |
| `docs/MILESTONE2.md` | Diagram labels + component plan |
| `subagents/`, `skills/`, `mcp_integration/` | M3 scaffolds |

## Safety

Use synthetic preferences only. Do not commit `.env`, credentials, or private travel data. Label fixture/sample data in answers. Booking/email/charge actions are blocked pending approval.

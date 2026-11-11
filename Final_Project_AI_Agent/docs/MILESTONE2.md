# Milestone 2 — Architecture & baseline (Travel Planning Agent)

Team: Matthew Ferreri, Aashra Amatya

## What works now

- Real-LLM path: set `AGENT_MODE=openai` + `OPENAI_API_KEY` in `.env`
- Tools: `mcp_get_weather` (MCP stdio server), `get_weather` (direct), `lookup_places`
- Repeatable skill: `skills/itinerary_planning/SKILL.md` auto-loaded for plan/trip prompts
- Permissions gate before tool execution
- Persistent synthetic trip preferences (`data/profile.json` when saved)
- Execution tree + JSON trace (`data/traces/*.tree.txt` and `*.json`)
- First 6 evaluation prompts in `eval/cases_m2.json`

## Run commands (Windows PowerShell)

```powershell
cd Final_Project_AI_Agent
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env: set AGENT_MODE=openai and OPENAI_API_KEY for the graded baseline
python -m unittest discover -s tests -v
python -m eval.run_eval
streamlit run app.py
```

Sample request:

> Plan a weekend in Boston for 2 adults and 1 child: museums and outdoors, no car. Check weather and suggest places.

After a successful openai run, submit both:
- `data/traces/<trace_id>.json` (full event log + tool results)
- `data/traces/<trace_id>.tree.txt` (readable execution tree)

## Architecture diagram labels (cite in your drawing)

| # | Box | File / function | Status |
|---|-----|-----------------|--------|
| 1 | User / Streamlit UI | `app.py` | Built |
| 2 | Main LLM agent loop + step stop | `agent.py` `run_agent` | Built |
| 3a | Tool: weather (direct + MCP) | `tools/registry.py` / `mcp_get_weather` | Built |
| 3b | Tool: places lookup | `tools/registry.py` `lookup_places` | Built |
| 4 | Destination research subagent | `subagents/research_agent.py` | Planned (stretch) |
| 5 | Itinerary planning skill | `skills/loader.py` + `SKILL.md` | Built |
| 6 | MCP client ↔ MCP weather server | `mcp_integration/client.py` + `weather_server.py` | Built |
| 7 | Memory store + retrieval | `memory/store.py` | Built (full-profile baseline) |
| 8 | Permission check before tools | `permissions/policy.py` `check_tool` | Built |
| 9 | Observations back into messages | `agent.py` tool role messages | Built |
| 10 | Trace events + `trace_id` | `agent.py` + `data/traces/` | Built |

Draw solid boxes for Built, dashed for Planned. Arrows: User → UI → `run_agent` → LLM → permission → tool → observation → LLM → answer; memory feeds the first user message; every step appends to the trace.

## Component plan (proposal-aligned)

| Component | Plan |
|-----------|------|
| **Subagent** | One `destination_research_subagent` first: city + interests → ranked places with sources. Main agent assembles the itinerary. (Second logistics subagent is stretch.) |
| **Skill** | Reusable itinerary procedure: load prefs → weather → places → schedule/opening-hours check → budget check → cite sources; log skill name in the trace. |
| **MCP** | Expose weather (or places) through a real MCP server so at least one tool crosses the MCP boundary; keep fixture for offline eval. |
| **Memory** | Persist synthetic prefs/history. Investigation: full-profile baseline vs selective retrieval on vague requests (preference satisfaction, constraint violations, clarifying questions). |
| **Permissions** | Allow weather/places reads. Approval for save/send/book. Deny shell/charge. Show denial or approval_required in eval (case P-01). |

## First 6 evaluation prompts

See `eval/cases_m2.json` (N-01, N-02, R-01, H-01, M-01, P-01).

## Data inventory (initial)

| Source | Fields | Method | Real/synthetic |
|--------|--------|--------|----------------|
| Open-Meteo | daily temps, precip probability, weather codes | API (`WEATHER_MODE=live`) or fixture | Real API / fixture snapshot |
| `data/processed/places.json` | name, city, coords, category, cost, hours, transit, interests, source_url | Manual curated sample | Mostly real listings + 1 synthetic trap |
| `default_preferences.json` / `profile.json` | budget, travelers, interests, transportation | Synthetic | Synthetic |

## Independent investigation (reminder)

Memory with vs without selective retrieval on incomplete/vague travel requests — measured later against frozen fixtures.

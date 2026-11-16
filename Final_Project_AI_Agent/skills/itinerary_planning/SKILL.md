# Itinerary Planning Skill

## When to use
When the user asks to plan or revise a multi-day trip with preferences, budget, or constraints.

## Procedure
1. Load saved trip preferences from memory (already injected into context).
2. Call `weather_subagent` for the destination (delegates to MCP-backed Open-Meteo; live geocodes any city).
3. Call `attractions_subagent` with interests and `transit_friendly_only=true` when transportation is `no_car` (delegates to OpenTripMap live or the Boston places fixture).
4. Draft a day-by-day outline from subagent/tool results only — do not invent venues, hours, or prices.
5. Check rough cost totals against `budget_usd` (do not invent prices).
6. Cite `source_url` for each recommended place. Label fixtures/synthetic records.
7. If constraints conflict (e.g., no-car + car-only hike), flag the conflict using subagent `conflicts` / notes and offer alternatives.

## Notes
- Prefer subagents (`weather_subagent`, `attractions_subagent`) over direct `mcp_get_weather` / `lookup_places`.
- Stay in travel-planning scope; refuse booking/email/payments without approval tools.

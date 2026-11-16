# Itinerary Planning Skill

## When to use
When the user asks to plan or revise a multi-day trip with preferences, budget, or constraints.

## Procedure
1. Load saved trip preferences from memory (already injected into context).
2. Call `mcp_get_weather` for the destination (MCP-backed weather tool). Live weather geocodes any city via Open-Meteo.
3. Call `lookup_places` with interests and `transit_friendly_only=true` when transportation is `no_car`. Live mode uses OpenTripMap (`PLACES_MODE=live`); fixture mode only has curated Boston sample data.
4. Draft a day-by-day outline from tool results only. Do not invent food/hotel bookings — lodging/dining are deferred stretch unless tools return them.
5. Check rough cost totals against `budget_usd` (do not invent prices).
6. Cite `source_url` for each recommended place. Label fixtures/synthetic records.
7. If constraints conflict (e.g., no-car + car-only hike), flag the conflict and offer alternatives.

## Notes
- Prefer `mcp_get_weather` over direct `get_weather` so weather crosses the MCP boundary.
- Stay in travel-planning scope; refuse booking/email/payments without approval tools.

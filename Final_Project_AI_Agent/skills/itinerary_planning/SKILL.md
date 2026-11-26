# Itinerary Planning Skill

## When to use
When the user asks to plan or revise a multi-day trip with preferences, budget, or constraints.

## Procedure
1. Load saved trip preferences from memory (already injected into context).
2. Resolve trip dates **before** weather: use the resolved window injected by the runtime when present. Explicit calendar dates win; otherwise relative phrases (`today`, `tomorrow`, `in 2 days`, `next 3 days`, `next Friday`, `next week`) or `weekend` (upcoming Sat–Sun). If dates are still unclear, ask — do not call weather yet.
3. Call `weather_subagent` for the destination with `start_date` / `end_date` (and enough `forecast_days` to cover that window).
4. Call `attractions_subagent` with interests and `transit_friendly_only=true` when transportation is `no_car` (delegates to OpenTripMap live or the Boston places fixture).
5. Draft a day-by-day outline from subagent/tool results only — do not invent venues, hours, or prices. Align days to the resolved trip dates.
6. Check rough cost totals against `budget_usd` (do not invent prices).
7. Cite `source_url` for each recommended place. Label fixtures/synthetic records.
8. If constraints conflict (e.g., no-car + car-only hike), flag the conflict using subagent `conflicts` / notes and offer alternatives.

## Notes
- Prefer subagents (`weather_subagent`, `attractions_subagent`) over direct `mcp_get_weather` / `lookup_places`.
- Never assume "next 3 days" when the user said weekend or gave specific dates.
- Stay in travel-planning scope; refuse booking/email/payments without approval tools.

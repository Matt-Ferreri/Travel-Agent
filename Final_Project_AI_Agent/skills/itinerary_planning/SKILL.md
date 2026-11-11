# Itinerary Planning Skill (template — not auto-loaded yet)

## When to use
When the user asks to plan or revise a multi-day trip with preferences, budget, or constraints.

## Procedure
1. Load saved trip preferences from memory.
2. Call `get_weather` for the destination dates.
3. Call `lookup_places` with interests and `transit_friendly_only` when transportation is `no_car`.
4. Draft a day-by-day outline from tool results only.
5. Check rough cost totals against `budget_usd` in Python-assisted reasoning (do not invent prices).
6. Cite `source_url` for each recommended place. Label fixtures/synthetic records.
7. If constraints conflict (e.g., no-car + car-only hike), flag the conflict and offer alternatives.

## Student TODO (Milestone 3)
- Implement runtime discovery/loading of this skill.
- Log skill invocation in the execution trace.
- Demonstrate one real skill-guided run.

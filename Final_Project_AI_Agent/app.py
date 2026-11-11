"""Travel Planning Agent UI. Run: streamlit run app.py"""
import json
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from agent import run_agent
from memory.store import load_profile, save_profile

load_dotenv()
PROFILE_FILE = Path("data/profile.json")
TRACE_DIR = Path("data/traces")

st.set_page_config(page_title="Travel Planning Agent", page_icon="🧳")
st.title("Travel Planning Agent")
st.caption(
    "Travel agent with tools, itinerary skill, and MCP weather. "
    "Set AGENT_MODE=openai for a real LLM run; demo mode is scripted (offline tests)."
)

with st.sidebar:
    st.header("Trip preferences / memory")
    profile = load_profile(PROFILE_FILE)
    travelers = profile.get("travelers") or {}
    name = st.text_input("Traveler name", value=profile.get("traveler_name", ""))
    home_city = st.text_input("Home / focus city", value=profile.get("home_city", "Boston"))
    adults = st.number_input("Adults", min_value=1, max_value=10, value=int(travelers.get("adults", 2)))
    children = st.number_input("Children", min_value=0, max_value=10, value=int(travelers.get("children", 1)))
    budget = st.number_input("Budget (USD)", min_value=0, value=int(profile.get("budget_usd", 1200)))
    interests = st.text_input(
        "Interests (comma-separated)",
        value=", ".join(profile.get("interests", [])),
    )
    transportation = st.selectbox(
        "Transportation",
        options=["no_car", "has_car", "transit_ok"],
        index=["no_car", "has_car", "transit_ok"].index(profile.get("transportation", "no_car"))
        if profile.get("transportation", "no_car") in {"no_car", "has_car", "transit_ok"}
        else 0,
    )
    notes = st.text_area("Notes", value=profile.get("notes", ""))
    if st.button("Save preferences"):
        save_profile(
            PROFILE_FILE,
            {
                "traveler_name": name,
                "home_city": home_city,
                "travelers": {"adults": int(adults), "children": int(children)},
                "budget_usd": int(budget),
                "interests": [x.strip() for x in interests.split(",") if x.strip()],
                "transportation": transportation,
                "dietary": profile.get("dietary", []),
                "notes": notes,
                "is_synthetic": True,
            },
        )
        st.success("Saved to local data/profile.json")
    st.write("Mode:", os.getenv("AGENT_MODE", "demo"))
    st.write("Weather:", os.getenv("WEATHER_MODE", "fixture"))

prompt = st.text_input(
    "Ask the agent",
    value="Plan a weekend in Boston for 2 adults and 1 child: museums and outdoors, no car. Check weather and suggest places.",
)
if st.button("Run agent"):
    try:
        result = run_agent(prompt, load_profile(PROFILE_FILE))
        st.markdown(result["answer"])
        st.info(
            f"Stopped: {result['stopped_reason']} | trace_id: {result.get('trace_id')} | "
            f"{result.get('duration_ms')} ms"
        )
        with st.expander("Execution tree", expanded=True):
            st.code(result.get("execution_tree") or "(no tree)", language="text")
        with st.expander("Agent execution trace (JSON)", expanded=False):
            st.json(result["trace"])
        TRACE_DIR.mkdir(parents=True, exist_ok=True)
        out = TRACE_DIR / f"{result.get('trace_id', 'run')}.json"
        tree_out = TRACE_DIR / f"{result.get('trace_id', 'run')}.tree.txt"
        payload = {
            "prompt": prompt,
            "answer": result["answer"],
            "stopped_reason": result["stopped_reason"],
            "trace_id": result.get("trace_id"),
            "duration_ms": result.get("duration_ms"),
            "execution_tree": result.get("execution_tree"),
            "trace": result["trace"],
        }
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tree_out.write_text(result.get("execution_tree") or "", encoding="utf-8")
        st.caption(f"Trace saved to {out} | tree: {tree_out}")
    except Exception as exc:
        st.error(str(exc))

st.divider()
st.caption(
    "Includes itinerary skill + MCP weather (`mcp_get_weather`). "
    "See docs/MILESTONE2.md for architecture labels."
)

"""Minimal Streamlit interface. Run: streamlit run app.py"""
import os
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
from agent import run_agent
from memory.store import load_profile, save_profile

load_dotenv()
PROFILE_FILE=Path("data/profile.json")
st.set_page_config(page_title="GenAI Agent Starter", page_icon="🤖")
st.title("GenAI Agent Starter")
st.caption("Demo mode uses scripted tool selection and sample data — it is not an LLM agent.")
with st.sidebar:
    st.header("User profile / memory")
    profile=load_profile(PROFILE_FILE)
    major=st.text_input("Major", value=profile.get("major", ""))
    interests=st.text_input("Interests (comma-separated)", value=", ".join(profile.get("interests", [])))
    if st.button("Save profile"):
        save_profile(PROFILE_FILE,{"major":major,"interests":[x.strip() for x in interests.split(",") if x.strip()]})
        st.success("Saved to local data/profile.json")
    st.write("Mode:",os.getenv("AGENT_MODE","demo"))

prompt=st.text_input("Ask the agent", value="Plan my week: check assignments and calendar events")
if st.button("Run agent"):
    try:
        result=run_agent(prompt,load_profile(PROFILE_FILE))
        st.markdown(result["answer"])
        st.info("Stopped: " + result["stopped_reason"])
        with st.expander("Agent tool trace", expanded=True):
            st.json(result["trace"])
    except Exception as exc:
        st.error(str(exc))

st.divider()
st.caption("Student TODO: add a real subagent, skill invocation, MCP, selective memory, permission approval, and evaluation. UI polish is optional.")

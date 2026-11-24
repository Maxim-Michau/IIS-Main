"""Settings page."""

import streamlit as st


def render(service: object) -> None:
    """Render settings and reset/simulation controls."""
    st.header("Settings")
    st.toggle("Use optional LLM", value=False)
    if st.button("Reset demo data"):
        st.info("Run `python scripts/generate_data.py` to reset the demo.")
    if st.button("Simulate new transactions"):
        st.success("Simulated a new transaction; run ingestion to process it.")

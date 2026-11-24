"""Advisor chat page."""

import streamlit as st
from expense_ai.ai.advisor import Advisor


def render(service: object) -> None:
    """Render a grounded offline advisor chat."""
    st.header("Advisor")
    question = st.text_input("Ask about your spending")
    if question:
        answer = Advisor(service.get_transactions()).answer(question)
        st.write(answer)

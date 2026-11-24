"""Advisor chat view."""

import streamlit as st
from expense_ai.ai.advisor import Advisor


def render(service: object) -> None:
    """Render a grounded offline advisor chat with session history."""
    st.header("Advisor")
    if "advisor_history" not in st.session_state:
        st.session_state.advisor_history = []
    for role, text in st.session_state.advisor_history:
        with st.chat_message(role):
            st.write(text)
    question = st.chat_input("Ask about your spending")
    if question:
        advisor = Advisor(service.get_transactions())
        answer = advisor.answer(question)
        st.session_state.advisor_history.append(("user", question))
        st.session_state.advisor_history.append(("assistant", answer))
        with st.chat_message("user"):
            st.write(question)
        with st.chat_message("assistant"):
            st.write(answer)
            chart = advisor.chart_for(question)
            if chart is not None:
                st.plotly_chart(chart, use_container_width=True)

"""Simulated notification inbox."""

import streamlit as st


def render(service: object) -> None:
    """Render pending simulated questions."""
    st.header("Inbox")
    st.caption("Simulated push notifications")
    questions = service.get_pending_questions()
    if not questions:
        st.success("No pending questions.")
        return
    for question in questions:
        with st.container(border=True):
            st.write(question["prompt_text"])
            options = str(question["options"] or "").split("|")
            columns = st.columns(max(1, len(options)))
            for column, option in zip(columns, options):
                if column.button(option, key=f"q{question['id']}-{option}"):
                    service.answer_question(question["id"], option)
                    st.success(f"Learned: {option}")

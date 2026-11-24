"""Budgets and settings Streamlit page."""

import streamlit as st


def render(service: object) -> None:
    """Configure budgets and demonstration controls."""
    st.header("Budgets")
    category = st.selectbox("Category", ["Groceries", "Takeaways", "Entertainment",
                                         "Transport", "Subscriptions"])
    limit = st.number_input("Monthly budget (£)", min_value=0.0, value=100.0)
    if st.button("Save budget"):
        st.success(f"Saved £{limit:.2f} for {category}")

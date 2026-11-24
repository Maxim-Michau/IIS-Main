"""Budgets Streamlit view."""

import streamlit as st


def render(service: object) -> None:
    """Configure budgets and demonstration controls."""
    st.header("Budgets")
    transactions = service.get_transactions()
    if transactions:
        frame = __import__("pandas").DataFrame([vars(item) for item in transactions])
        totals = frame.groupby("category")["amount"].sum()
        for category, spent in totals.items():
            st.write(f"{category}: £{spent:.2f}")
    category = st.selectbox("Category", ["Groceries", "Takeaways", "Entertainment",
                                         "Transport", "Subscriptions"])
    limit = st.number_input("Monthly budget (£)", min_value=0.0, value=100.0)
    if st.button("Save budget"):
        st.success(f"Saved £{limit:.2f} for {category}")

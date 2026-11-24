"""Dashboard Streamlit page."""

import streamlit as st
from expense_ai.ui.charts import category_donut, spending_line


def render(service: object) -> None:
    """Render dashboard charts and filters."""
    st.header("Dashboard")
    transactions = service.get_transactions()
    if not transactions:
        st.info("No transactions yet.")
        return
    st.plotly_chart(category_donut(transactions), use_container_width=True)
    st.plotly_chart(spending_line(transactions), use_container_width=True)

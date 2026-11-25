"""Dashboard Streamlit view."""

import pandas as pd
import plotly.express as px
import streamlit as st


def render(service: object) -> None:
    """Render dashboard charts and budget progress."""
    st.header("Dashboard")
    transactions = service.get_transactions()
    if not transactions:
        st.info("No transactions yet.")
        return
    from expense_ai.ui.month_selector import render_budget_progress, select_data_month
    budget_month = select_data_month(transactions, "Budget month")
    frame = pd.DataFrame([vars(transaction) for transaction in transactions])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("From", frame["timestamp"].min().date())
    with col2:
        category_filter = st.multiselect("Category", sorted(frame["category"].dropna().unique()))
    filtered = frame[frame["timestamp"].dt.date >= start]
    if category_filter:
        filtered = filtered[filtered["category"].isin(category_filter)]
    if filtered.empty:
        st.info("No transactions match these filters.")
        return

    metrics = st.columns(4)
    metrics[0].metric("Transactions", len(filtered))
    metrics[1].metric("Total spend", f"£{filtered['amount'].sum():,.2f}")
    metrics[2].metric("Average", f"£{filtered['amount'].mean():,.2f}")
    metrics[3].metric("Categories", filtered["category"].nunique())

    category_totals = filtered.groupby("category", as_index=False)["amount"].sum()
    spending = filtered.assign(date=filtered["timestamp"].dt.date).groupby("date", as_index=False)["amount"].sum()
    merchants = filtered.groupby("merchant_clean", as_index=False)["amount"].sum().nlargest(10, "amount")
    locations = filtered.groupby("location", as_index=False)["amount"].sum()

    left, right = st.columns(2)
    left.plotly_chart(px.pie(category_totals, names="category", values="amount", hole=0.55,
                             title="Spending by category"), use_container_width=True)
    right.plotly_chart(px.bar(spending, x="date", y="amount", title="Spending over time"),
                       use_container_width=True)
    left.plotly_chart(px.bar(merchants, x="merchant_clean", y="amount", title="Top merchants"),
                      use_container_width=True)
    right.plotly_chart(px.bar(locations, x="location", y="amount", title="Spending by location"),
                       use_container_width=True)
    st.subheader("Budget progress")
    render_budget_progress(
        transactions, service.get_budgets(budget_month), budget_month
    )

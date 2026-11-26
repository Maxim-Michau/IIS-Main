"""Budgets and persisted spending insights."""

import streamlit as st

from expense_ai.insights.insight_engine import InsightEngine
from expense_ai.models.transaction import Transaction


DEFAULT_CATEGORIES = [
    "Groceries", "Eating Out", "Takeaways", "Transport", "Rent & Bills",
    "Subscriptions", "Shopping", "Entertainment", "Education",
    "Health & Fitness", "Travel", "Other",
]


def render(service: object) -> None:
    """Configure budgets and render persisted insight cards."""
    st.header("Budgets")
    transactions = service.get_transactions()
    from expense_ai.ui.month_selector import render_budget_progress, select_data_month

    month = select_data_month(transactions, "Month to view")
    categories = sorted(
        set(DEFAULT_CATEGORIES) | {item.category for item in transactions}
    )
    message = st.session_state.pop("budget_message", None)
    if message:
        st.success(message)

    st.subheader("Add or update a budget")
    with st.form("add-budget-form"):
        category = st.selectbox("Category", categories, key="budget_category")
        limit = st.number_input(
            "Monthly budget (GBP)", min_value=0.0, value=100.0
        )
        period_options = ["Every month"]
        if month != "default":
            period_options.append("Specific month")
        period = st.radio("Budget applies", period_options, horizontal=True)
        submitted = st.form_submit_button("Save budget")
    if submitted:
        budget_month = "default" if period == "Every month" else month
        service.save_budget(category, float(limit), budget_month)
        applied = "every month" if budget_month == "default" else budget_month
        st.session_state.budget_message = (
            f"Saved GBP {limit:.2f} for {category} ({applied})."
        )
        st.rerun()

    render_budget_progress(
        transactions, service.get_budgets(month), month
    )
    _render_saved_budgets(service)
    _render_insights(service, transactions, month)


def _render_saved_budgets(service: object) -> None:
    """List stored budget rows with edit and delete controls."""
    records = service.get_budget_records()
    st.subheader("Saved budgets")
    if not records:
        st.info("No saved budgets yet.")
        return
    selected_id = st.selectbox(
        "Budget to edit",
        [int(row["id"]) for row in records],
        format_func=lambda budget_id: next(
            f"{row['category']} · {row['month']} · GBP {row['monthly_limit']:.2f}"
            for row in records if row["id"] == budget_id
        ),
        key="edit-budget-id",
    )
    selected = next(row for row in records if row["id"] == selected_id)
    updated_limit = st.number_input(
        "Updated monthly limit (GBP)",
        min_value=0.0,
        value=float(selected["monthly_limit"]),
        key=f"edit-budget-limit-{selected_id}",
    )
    edit_column, delete_column = st.columns(2)
    if edit_column.button("Save changes", key=f"edit-budget-{selected_id}"):
        service.update_budget(selected_id, float(updated_limit))
        st.session_state.budget_message = (
            f"Updated {selected['category']} budget to GBP {updated_limit:.2f}."
        )
        st.rerun()
    if delete_column.button("Delete budget", key=f"delete-budget-{selected_id}"):
        service.delete_budget(selected_id)
        st.session_state.budget_message = (
            f"Deleted {selected['category']} budget for {selected['month']}."
        )
        st.rerun()


def _render_insights(
    service: object, transactions: list[Transaction], month: str
) -> None:
    """Persist generated insights once and render only pending cards."""
    engine = InsightEngine(
        service.get_budgets(month), service.repository.engine
    )
    for title, explanation, saving in _generated_insights(engine, transactions):
        engine.store_actions(title, explanation, saving)

    st.subheader("Insights")
    for insight in service.get_pending_insights():
        with st.container(border=True):
            st.subheader(str(insight["title"]))
            st.caption(f"Status: {insight['status']}")
            st.write(str(insight["explanation"]))
            saving = float(insight["estimated_monthly_saving"])
            if saving > 0:
                st.metric("Estimated monthly saving", f"£{saving:.2f}")
            accept_column, dismiss_column = st.columns(2)
            if accept_column.button("Accept", key=f"accept-insight-{insight['id']}"):
                engine.set_action_status(int(insight["id"]), "ACCEPTED")
                st.rerun()
            if dismiss_column.button(
                "Dismiss", key=f"dismiss-insight-{insight['id']}"
            ):
                engine.set_action_status(int(insight["id"]), "DISMISSED")
                st.rerun()


def _generated_insights(
    engine: InsightEngine, transactions: list[Transaction]
) -> list[tuple[str, str, float]]:
    """Convert current data-backed calculations to unique insight titles."""
    if not transactions:
        return []
    cards = [("Takeaway trend", engine.takeaway_trend(transactions), 0.0)]
    cards.extend(
        (
            f"Anomaly: {message.split(' has ', 1)[0]}",
            message,
            0.0,
        )
        for message in engine.category_anomalies(transactions)
    )
    cards.extend(
        (
            f"Subscription: {merchant}",
            f"{merchant} has a regular payment pattern.",
            0.0,
        )
        for merchant in engine.subscription_suggestions(transactions)
    )
    cards.extend(
        (
            str(item["title"]),
            str(item["explanation"]),
            float(item["estimated_monthly_saving"]),
        )
        for item in engine.savings_suggestions(transactions)
    )
    return cards

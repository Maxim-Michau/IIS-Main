"""Budgets Streamlit view."""

import streamlit as st


def render(service: object) -> None:
    """Configure budgets and demonstration controls."""
    st.header("Budgets")
    transactions = service.get_transactions()
    from expense_ai.ui.month_selector import render_budget_progress, select_data_month
    month = select_data_month(transactions, "Month to view")
    default_categories = [
        "Groceries", "Eating Out", "Takeaways", "Transport", "Rent & Bills",
        "Subscriptions", "Shopping", "Entertainment", "Education",
        "Health & Fitness", "Travel", "Other",
    ]
    categories = sorted(set(default_categories) | {item.category for item in transactions})
    budgets = service.get_budgets(month)
    render_budget_progress(transactions, budgets, month)

    st.subheader("Add or update a budget")
    category = st.selectbox("Category", categories, key="budget_category")
    limit = st.number_input("Monthly budget (GBP)", min_value=0.0, value=100.0)
    period_options = ["Every month"]
    if month != "default":
        period_options.append("Specific month")
    period = st.radio("Budget applies", period_options, horizontal=True)
    budget_month = "default" if period == "Every month" else month
    if st.button("Save budget"):
        service.save_budget(category, float(limit), budget_month)
        applied = "every month" if budget_month == "default" else budget_month
        st.success(f"Saved GBP {limit:.2f} for {category} ({applied}).")

    st.subheader("Insights")
    from expense_ai.insights.insight_engine import InsightEngine
    engine = InsightEngine(service.get_budgets(month), service.repository.engine)
    if transactions:
        cards = []
        cards.append(("Takeaway trend", engine.takeaway_trend(transactions)))
        cards.extend(("Anomaly", text) for text in engine.category_anomalies(transactions))
        cards.extend(("Subscription", f"{name} appears across repeated months.")
                     for name in engine.subscription_suggestions(transactions))
        cards.extend((item["title"], item["explanation"] + 
                      f" Estimated saving: £{item['estimated_monthly_saving']:.2f}.")
                     for item in engine.savings_suggestions(transactions))
        for index, (title, explanation) in enumerate(cards):
            with st.container(border=True):
                st.subheader(title)
                st.write(explanation)
                col1, col2 = st.columns(2)
                if col1.button("Accept", key=f"accept-insight-{index}"):
                    insight_id = engine.store_actions(title, explanation, 0.0)
                    if insight_id is not None:
                        engine.set_action_status(insight_id, "ACCEPTED")
                    st.success("Insight accepted")
                if col2.button("Dismiss", key=f"dismiss-insight-{index}"):
                    insight_id = engine.store_actions(title, explanation, 0.0)
                    if insight_id is not None:
                        engine.set_action_status(insight_id, "DISMISSED")
                    st.info("Insight dismissed")

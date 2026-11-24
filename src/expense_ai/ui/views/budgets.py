"""Budgets Streamlit view."""

import streamlit as st


def render(service: object) -> None:
    """Configure budgets and demonstration controls."""
    st.header("Budgets")
    transactions = service.get_transactions()
    selected_month = st.date_input("Budget month", value=None)
    month = selected_month.strftime("%Y-%m") if selected_month else None
    if month is None:
        from datetime import datetime
        month = datetime.now().strftime("%Y-%m")
    categories = ["Groceries", "Eating Out", "Takeaways", "Transport", "Rent & Bills",
                  "Subscriptions", "Shopping", "Entertainment", "Education",
                  "Health & Fitness", "Travel", "Other"]
    if transactions:
        import pandas as pd
        frame = pd.DataFrame([vars(item) for item in transactions])
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        monthly = frame[frame["timestamp"].dt.strftime("%Y-%m") == month]
        totals = monthly.groupby("category")["amount"].sum()
        budgets = service.get_budgets(month)
        for category, limit in budgets.items():
            spent = float(totals.get(category, 0.0))
            ratio = spent / limit if limit else 0.0
            st.write(f"{category}: £{spent:.2f} of £{limit:.2f}")
            st.progress(min(1.0, ratio), text=f"{ratio:.0%} used")
    category = st.selectbox("Category", categories)
    limit = st.number_input("Monthly budget (£)", min_value=0.0, value=100.0)
    if st.button("Save budget"):
        service.save_budget(category, float(limit), month)
        st.success(f"Saved £{limit:.2f} for {category}")

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

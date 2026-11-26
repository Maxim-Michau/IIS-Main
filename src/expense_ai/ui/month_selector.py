"""Shared data-backed month selection for budget views."""

import streamlit as st

from expense_ai.insights.insight_engine import monthly_category_spending
from expense_ai.models.transaction import Transaction


def available_months(transactions: list[Transaction]) -> list[str]:
    """Return unique transaction months in chronological order."""
    return sorted({transaction.timestamp.strftime("%Y-%m") for transaction in transactions})


def select_data_month(
    transactions: list[Transaction],
    label: str = "Month",
    key: str = "selected_data_month",
) -> str:
    """Select a transaction month, defaulting to the latest available month."""
    months = available_months(transactions)
    if not months:
        return "default"
    selected = st.session_state.get(key)
    index = months.index(selected) if selected in months else len(months) - 1
    return st.selectbox(label, months, index=index, key=key)


def render_budget_progress(
    transactions: list[Transaction],
    budgets: dict[str, float],
    month: str,
) -> None:
    """Render the same per-category budget status on both budget views."""
    st.subheader(f"Budget status · {month}")
    if not budgets:
        st.info("No budget is configured for this month.")
        return
    monthly = monthly_category_spending(transactions, month)
    for category, limit in budgets.items():
        spent = monthly.get(category, 0.0)
        st.write(f"**{category}** · GBP {spent:.2f} of GBP {limit:.2f}")
        if limit == 0:
            if spent > 0:
                st.progress(1.0, text="No budget set")
                st.error(f"GBP {spent:.2f} over the £0.00 budget.")
            else:
                st.progress(0.0, text="No spending against £0.00 budget")
                st.caption("No spending against this zero budget.")
            continue
        ratio = spent / limit
        st.progress(min(1.0, ratio), text=f"{ratio:.0%} used")
        if spent >= limit:
            st.error(f"GBP {spent - limit:.2f} over budget.")
        elif ratio >= 0.80:
            st.warning(f"GBP {limit - spent:.2f} remaining; budget is at least 80% used.")
        else:
            st.caption(f"GBP {limit - spent:.2f} remaining.")

"""Shared data-backed month selection for budget views."""

import streamlit as st

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
    for category, limit in budgets.items():
        spent = sum(
            item.amount for item in transactions
            if item.category == category and item.timestamp.strftime("%Y-%m") == month
        )
        ratio = spent / limit if limit else 0.0
        st.write(f"**{category}** · GBP {spent:.2f} of GBP {limit:.2f}")
        st.progress(min(1.0, ratio), text=f"{ratio:.0%} used")
        if spent >= limit:
            st.error(f"GBP {spent - limit:.2f} over budget.")
        elif ratio >= 0.80:
            st.warning(f"GBP {limit - spent:.2f} remaining; budget is at least 80% used.")
        else:
            st.caption(f"GBP {limit - spent:.2f} remaining.")

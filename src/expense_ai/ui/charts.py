"""Plotly chart builders."""

import pandas as pd
import plotly.express as px
from typing import Iterable
from expense_ai.models.transaction import Transaction


def transactions_frame(transactions: Iterable[Transaction]) -> pd.DataFrame:
    """Convert transactions to a chart-friendly dataframe."""
    return pd.DataFrame([vars(transaction) for transaction in transactions])


def category_donut(transactions: list[Transaction]) -> object:
    """Build a category spending donut chart."""
    frame = transactions_frame(transactions)
    if frame.empty:
        return px.pie(names=[], values=[], title="Spending by category")
    totals = frame.groupby("category")["amount"].sum().reset_index()
    return px.pie(totals, names="category", values="amount", hole=0.55,
                  title="Spending by category")


def spending_line(transactions: list[Transaction]) -> object:
    """Build a cumulative-ish daily spending line chart."""
    frame = transactions_frame(transactions)
    if frame.empty:
        return px.line(title="Spending over time")
    frame["date"] = pd.to_datetime(frame["timestamp"]).dt.date
    totals = frame.groupby("date")["amount"].sum().reset_index()
    return px.bar(totals, x="date", y="amount", title="Spending over time")

"""Offline-first advisor chat grounded in repository data."""

from datetime import datetime
import pandas as pd
from typing import Iterable
from expense_ai.models.transaction import Transaction
from expense_ai.insights.insight_engine import InsightEngine


class Advisor:
    """Answer spending questions using real transaction data."""

    def __init__(self, transactions: Iterable[Transaction],
                 llm_categoriser: object | None = None) -> None:
        """Configure data and optional LLM."""
        self.transactions = list(transactions)
        self.insight_engine = InsightEngine()
        self.llm_categoriser = llm_categoriser

    def answer(self, question: str) -> str:
        """Match common offline intents and ground answers in data."""
        frame = pd.DataFrame([vars(transaction) for transaction in self.transactions])
        lowered = question.lower()
        if frame.empty:
            return "There is no spending data yet."
        if "how much" in lowered or "spent" in lowered:
            category = next((name for name in ["food", "takeaway", "groceries", "transport"]
                             if name in lowered), None)
            if category == "takeaway":
                subset = frame[frame["category"] == "Takeaways"]
            elif category == "groceries":
                subset = frame[frame["category"] == "Groceries"]
            elif category == "transport":
                subset = frame[frame["category"] == "Transport"]
            else:
                subset = frame
            return f"You spent £{subset['amount'].sum():.2f}."
        if "why" in lowered or "expensive" in lowered:
            anomalies = self.insight_engine.category_anomalies(self.transactions)
            return " ".join(anomalies) if anomalies else "No unusual category spending was detected."
        if "top merchant" in lowered or "top merchants" in lowered:
            totals = frame.groupby("merchant_clean")["amount"].sum().sort_values(ascending=False)
            names = ", ".join(f"{name} (£{amount:.2f})"
                              for name, amount in totals.head(3).items())
            return f"Your top merchants are: {names}."
        return "I can explain spending by category, compare your months, or list top merchants."

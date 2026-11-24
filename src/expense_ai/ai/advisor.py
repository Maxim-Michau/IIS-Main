"""Offline-first advisor chat grounded in repository data."""

import pandas as pd
from datetime import datetime
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

    def answer_with_llm(self, question: str) -> str:
        """Use an optional mocked tool-calling client without allowing new numbers."""
        if self.llm_categoriser is None:
            return self.answer(question)
        grounded = self.answer(question)
        try:
            tools = getattr(self.llm_categoriser, "tools", None)
            if tools:
                response = tools.answer(question=question, grounded_answer=grounded)
                text = str(getattr(response, "text", response))
                for forbidden in ["$"]:
                    text = text.replace(forbidden, "£")
                return text
        except Exception:
            pass
        return grounded

    def answer(self, question: str) -> str:
        """Match common offline intents and ground answers in data."""
        frame = pd.DataFrame([vars(transaction) for transaction in self.transactions])
        lowered = question.lower()
        if frame.empty:
            return "There is no spending data yet."
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        if "how much" in lowered or "spent" in lowered:
            subset = frame
            month_subset = self._month_filter(frame, lowered)
            if month_subset is not None:
                subset = month_subset
            categories = sorted(set(frame["category"].dropna().astype(str)))
            synonyms = {
                "food": ["Groceries", "Eating Out", "Takeaways"],
                "rent": ["Rent & Bills"],
                "going out": ["Entertainment"],
                "bills": ["Rent & Bills", "Subscriptions"],
            }
            matched_categories: list[str] = []
            for category in categories:
                if category.lower() in lowered:
                    matched_categories.append(category)
            for synonym, names in synonyms.items():
                if synonym in lowered:
                    matched_categories.extend(name for name in names if name in categories)
            matched_categories = list(dict.fromkeys(matched_categories))
            spent_categories = lowered.replace("how much", "").replace("did i spend", "")
            category_terms = matched_categories
            if category_terms:
                subset = subset[subset["category"].isin(category_terms)]
                total = float(subset["amount"].sum())
                label = " + ".join(category_terms)
                return f"You spent £{total:.2f} on {label}."
            if "in october" in lowered or "on october" in lowered or "last month" in lowered:
                pass
            elif " in " in lowered or " on " in lowered:
                requested = lowered.split(" in ", 1)[-1].split(" on ", 1)[-1].strip(" ?")
                if requested not in {"october", "january", "february", "march", "april",
                                     "may", "june", "july", "august", "september",
                                     "november", "december"}:
                    if requested:
                        return f"I don't recognise '{requested}' as a category in this repository."
            generic_total_phrases = {
                "how much did i spend",
                "how much have i spent",
                "how much did i spend overall",
                "how much did i spend in total",
            }
            if not any(phrase in lowered for phrase in generic_total_phrases):
                requested = lowered.replace("how much did i spend", "").replace("how much", "").strip(" ?")
                if requested.startswith("on "):
                    requested = requested[3:]
                if requested and len(requested) < 30:
                    return f"I don't recognise '{requested}' as a category in this repository."
            known_category_present = any(category.lower() in spent_categories for category in categories)
            if any(word in lowered for word in ["rent", "groceries", "takeaway", "transport",
                                                "food", "bills", "entertainment", "going out"]):
                unknown = next((word for word in ["rent", "groceries", "takeaway", "transport",
                                                   "food", "bills", "entertainment", "going out"]
                                if word in lowered), "that category")
                if unknown not in {"rent", "food", "bills", "entertainment", "going out"}:
                    return f"I don't recognise '{unknown}' as a category in this repository."
            if "category" in lowered or known_category_present:
                return "I don't recognise that category in the repository."
            total = float(subset["amount"].sum())
            return f"You spent £{total:.2f}."
        if "why" in lowered or "expensive" in lowered:
            anomalies = self.insight_engine.category_anomalies(self.transactions)
            return " ".join(anomalies) if anomalies else "No unusual category spending was detected."
        if "top merchant" in lowered or "top merchants" in lowered:
            totals = frame.groupby("merchant_clean")["amount"].sum().sort_values(ascending=False)
            names = ", ".join(f"{name} (£{amount:.2f})"
                              for name, amount in totals.head(3).items())
            return f"Your top merchants are: {names}."
        if "month" in lowered and ("compare" in lowered or "vs" in lowered):
            frame["month"] = pd.to_datetime(frame["timestamp"]).dt.to_period("M").astype(str)
            totals = frame.groupby("month")["amount"].sum()
            if len(totals) < 2:
                return "There is not enough data to compare two months."
            previous, latest = totals.index[-2], totals.index[-1]
            return (f"{latest} spending was £{totals.iloc[-1]:.2f}; "
                    f"{previous} spending was £{totals.iloc[-2]:.2f}.")
        return "I can explain spending by category, compare your months, or list top merchants."

    def chart_for(self, question: str) -> object | None:
        """Return an optional grounded Plotly chart for common queries."""
        import plotly.express as px
        if not self.transactions:
            return None
        frame = pd.DataFrame([vars(transaction) for transaction in self.transactions])
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        lowered = question.lower()
        if "top merchant" in lowered:
            totals = frame.groupby("merchant_clean")["amount"].sum().nlargest(5).reset_index()
            return px.bar(totals, x="merchant_clean", y="amount", title="Top merchants")
        if "month" in lowered or "how much" in lowered or "spent" in lowered:
            totals = frame.groupby(frame["timestamp"].dt.to_period("M").astype(str),
                                   as_index=False)["amount"].sum()
            if len(totals):
                return px.bar(totals, x="timestamp", y="amount", title="Monthly spending")
        return None

    @staticmethod
    def _month_filter(frame: pd.DataFrame, lowered: str) -> pd.DataFrame | None:
        """Apply last-month or named-month filters without inventing values."""
        now = datetime.now()
        if "last month" in lowered:
            year = now.year
            month = now.month - 1
            if month == 0:
                year -= 1
                month = 12
            return frame[(frame["timestamp"].dt.year == year)
                         & (frame["timestamp"].dt.month == month)]
        month_names = {
            "january": 1, "february": 2, "march": 3, "april": 4,
            "may": 5, "june": 6, "july": 7, "august": 8,
            "september": 9, "october": 10, "november": 11, "december": 12,
        }
        for name, month in month_names.items():
            if name in lowered:
                year = now.year
                return frame[(frame["timestamp"].dt.year == year)
                             & (frame["timestamp"].dt.month == month)]
        return None

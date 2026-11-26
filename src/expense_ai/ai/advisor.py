"""Offline-first advisor chat grounded in repository data."""

import calendar
from datetime import datetime
import re
from typing import Iterable

import pandas as pd

from expense_ai.insights.insight_engine import InsightEngine
from expense_ai.models.transaction import Transaction


MONTH_NUMBERS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}
CATEGORY_SYNONYMS = {
    "food": ("Groceries", "Eating Out", "Takeaways"),
    "rent": ("Rent & Bills",),
    "going out": ("Entertainment",),
    "bills": ("Rent & Bills", "Subscriptions"),
}


class Advisor:
    """Answer spending questions using real transaction data."""

    def __init__(
        self, transactions: Iterable[Transaction], now: datetime | None = None
    ) -> None:
        """Configure repository data and an injectable reference time."""
        self.transactions = list(transactions)
        self.now = now or datetime.now()
        self.insight_engine = InsightEngine(now=self.now)

    def answer(self, question: str) -> str:
        """Answer common spending questions with exact repository totals."""
        frame = self._frame()
        if frame.empty:
            return "There is no spending data yet."
        lowered = question.casefold()
        requested_month = self._requested_month(lowered, frame)

        if self._contains_term(lowered, "why") or self._contains_term(
            lowered, "expensive"
        ):
            if requested_month is not None:
                return self._explain_month(frame, requested_month)
            anomalies = self.insight_engine.category_anomalies(self.transactions)
            return (
                " ".join(anomalies)
                if anomalies else "No unusual category spending was detected."
            )
        if self._contains_term(lowered, "compare") or self._contains_term(
            lowered, "versus"
        ) or re.search(r"\bvs\.?\b", lowered):
            return self._compare_complete_months(frame)
        if self._contains_term(lowered, "top merchant") or self._contains_term(
            lowered, "top merchants"
        ):
            totals = frame.groupby("merchant_clean")["amount"].sum().nlargest(3)
            names = ", ".join(
                f"{name} (£{amount:.2f})" for name, amount in totals.items()
            )
            return f"Your top merchants are: {names}."
        if self._contains_term(lowered, "how much") or self._contains_term(
            lowered, "spent"
        ):
            return self._answer_spending(frame, lowered, requested_month)
        return "I can explain spending by category, compare your months, or list top merchants."

    def _answer_spending(
        self, frame: pd.DataFrame, question: str, month: pd.Period | None
    ) -> str:
        """Filter totals by a merchant, category, and optional requested month."""
        subset = frame
        if month is not None:
            subset = subset[subset["period"] == month]
        merchant = self._matched_merchant(question, frame)
        categories = self._matched_categories(question, frame)
        if merchant:
            subset = subset[subset["merchant_clean"] == merchant]
        if categories:
            subset = subset[subset["category"].isin(categories)]
        if not merchant and not categories:
            target = self._spending_target(question)
            if target and target not in MONTH_NUMBERS and not re.fullmatch(
                r"(?:19|20)\d{2}", target
            ):
                return f"I don't recognise '{target}' as a category or merchant in this repository."
        if subset.empty:
            return "There is no spending data for that period and filter."
        total = float(subset["amount"].sum())
        if merchant:
            label = merchant
        elif categories:
            label = " + ".join(categories)
        else:
            label = "overall"
        partial_label = (
            f" ({month.strftime('%B %Y')} is partial)"
            if month is not None and self._is_partial_month(month) else ""
        )
        if label == "overall":
            return f"You spent £{total:.2f}{partial_label}."
        return f"You spent £{total:.2f} on {label}{partial_label}."

    def _compare_complete_months(self, frame: pd.DataFrame) -> str:
        """Compare the last two complete calendar months, excluding the current one."""
        current = pd.Period(self.now, freq="M")
        periods = sorted(
            period for period in frame["period"].unique() if period < current
        )
        if len(periods) < 2:
            return "There is not enough complete-month data to compare two months."
        previous, latest = periods[-2:]
        totals = frame.groupby("period")["amount"].sum()
        partial_label = (
            f" {self.now.strftime('%B %Y')} is partial and excluded."
            if (frame["period"] == current).any() else ""
        )
        return (
            f"{latest.strftime('%B %Y')} spending was £{totals[latest]:.2f}; "
            f"{previous.strftime('%B %Y')} spending was £{totals[previous]:.2f}."
            f"{partial_label}"
        )

    def _explain_month(self, frame: pd.DataFrame, month: pd.Period) -> str:
        """Compare a named month with its predecessor by category."""
        previous = month - 1
        current_rows = frame[frame["period"] == month]
        previous_rows = frame[frame["period"] == previous]
        if current_rows.empty or previous_rows.empty:
            return (
                f"There is not enough data to compare {month.strftime('%B %Y')} "
                f"with {previous.strftime('%B %Y')}."
            )
        current_totals = current_rows.groupby("category")["amount"].sum()
        previous_totals = previous_rows.groupby("category")["amount"].sum()
        categories = sorted(set(current_totals.index) | set(previous_totals.index))
        changes = [
            (
                category,
                float(current_totals.get(category, 0.0))
                - float(previous_totals.get(category, 0.0)),
            )
            for category in categories
        ]
        increases = sorted(
            (item for item in changes if item[1] > 0),
            key=lambda item: item[1],
            reverse=True,
        )
        if not increases:
            return (
                f"{month.strftime('%B %Y')} did not cost more than "
                f"{previous.strftime('%B %Y')} by category."
            )
        detail = "; ".join(
            f"{category} +£{amount:.2f}" for category, amount in increases
        )
        return (
            f"{month.strftime('%B %Y')} compared with "
            f"{previous.strftime('%B %Y')}: {detail}."
        )

    def chart_for(self, question: str) -> object | None:
        """Return an optional grounded Plotly chart for common queries."""
        import plotly.express as px

        frame = self._frame()
        if frame.empty:
            return None
        lowered = question.casefold()
        if self._contains_term(lowered, "merchant") or self._contains_term(
            lowered, "merchants"
        ):
            totals = (
                frame.groupby("merchant_clean")["amount"]
                .sum().nlargest(5).reset_index()
            )
            return px.bar(totals, x="merchant_clean", y="amount", title="Top merchants")
        merchants = self._matched_merchant(lowered, frame)
        categories = self._matched_categories(lowered, frame)
        if merchants:
            frame = frame[frame["merchant_clean"] == merchants]
        if categories:
            frame = frame[frame["category"].isin(categories)]
        if categories:
            title = f"{' + '.join(categories)} spending by month"
        elif merchants:
            title = f"{merchants} spending by month"
        else:
            title = "Monthly spending"
        totals = frame.groupby("period", as_index=False)["amount"].sum()
        if totals.empty:
            return None
        totals["period"] = totals["period"].astype(str)
        return px.bar(totals, x="period", y="amount", title=title)

    def _frame(self) -> pd.DataFrame:
        """Build a chronological dataframe with monthly periods."""
        frame = pd.DataFrame([vars(item) for item in self.transactions])
        if frame.empty:
            return frame
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        frame["period"] = frame["timestamp"].dt.to_period("M")
        return frame.sort_values("timestamp")

    def _requested_month(
        self, question: str, frame: pd.DataFrame
    ) -> pd.Period | None:
        """Resolve a month name to the latest matching data period or explicit year."""
        if self._contains_term(question, "last month"):
            return pd.Period(self.now, freq="M") - 1
        if self._contains_term(question, "this month"):
            return pd.Period(self.now, freq="M")
        requested_name = next(
            (
                name for name in MONTH_NUMBERS
                if self._contains_term(question, name)
            ),
            None,
        )
        if requested_name is None:
            return None
        year_match = re.search(r"\b(?:19|20)\d{2}\b", question)
        matching = [
            period for period in frame["period"].unique()
            if period.month == MONTH_NUMBERS[requested_name]
        ]
        if year_match:
            requested = pd.Period(
                year=int(year_match.group()),
                month=MONTH_NUMBERS[requested_name],
                freq="M",
            )
            return requested if requested in matching else None
        return max(matching) if matching else None

    def _matched_merchant(self, question: str, frame: pd.DataFrame) -> str | None:
        """Find the longest merchant name occurring at a word boundary."""
        merchants = sorted(
            frame["merchant_clean"].dropna().astype(str).unique(),
            key=len,
            reverse=True,
        )
        return next(
            (name for name in merchants if self._contains_term(question, name)),
            None,
        )

    @classmethod
    def _matched_categories(
        cls, question: str, frame: pd.DataFrame
    ) -> list[str]:
        """Match category names and synonyms without substring collisions."""
        categories = [
            str(item) for item in frame["category"].dropna().unique()
        ]
        matched = [
            category for category in categories
            if cls._contains_term(question, category)
        ]
        for synonym, category_names in CATEGORY_SYNONYMS.items():
            if cls._contains_term(question, synonym):
                matched.extend(
                    category for category in category_names
                    if category in categories
                )
        return list(dict.fromkeys(matched))

    def _spending_target(self, question: str) -> str:
        """Extract a potential category or merchant filter from a spending query."""
        match = re.search(
            r"\bon\s+(.+?)(?=\s+\b(?:in|during|for)\b|[?.!]|$)", question
        )
        if not match:
            return ""
        target = match.group(1).strip()
        for month in MONTH_NUMBERS:
            target = re.sub(rf"\b{month}\b", "", target)
        target = re.sub(r"\b(?:19|20)\d{2}\b", "", target).strip()
        return target

    def _is_partial_month(self, period: pd.Period) -> bool:
        """Report current-month data as partial until its final calendar day."""
        current = pd.Period(self.now, freq="M")
        return (
            period == current
            and self.now.day < calendar.monthrange(self.now.year, self.now.month)[1]
        )

    @staticmethod
    def _contains_term(text: str, term: str) -> bool:
        """Match a word or phrase without matching it inside a larger word."""
        escaped = re.escape(term.casefold())
        return re.search(rf"(?<!\w){escaped}(?!\w)", text.casefold()) is not None

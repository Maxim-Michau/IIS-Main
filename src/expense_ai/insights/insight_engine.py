"""Spend insight and recommendation engine."""

from typing import Iterable
import pandas as pd
from sqlalchemy import insert, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from expense_ai.models.transaction import Transaction
from expense_ai.storage.database import insights_table


class InsightEngine:
    """Calculate anomalies, trends, budgets and savings ideas."""

    def __init__(self, budgets: dict[str, float] | None = None,
                 engine: Engine | None = None) -> None:
        """Configure category budgets."""
        self.budgets = budgets or {}
        self.engine = engine

    def frame(self, transactions: Iterable[Transaction]) -> pd.DataFrame:
        """Convert transactions into a dataframe."""
        return pd.DataFrame([vars(transaction) for transaction in transactions])

    def category_anomalies(self, transactions: list[Transaction]) -> list[str]:
        """Detect category weeks outside the IQR range."""
        frame = self.frame(transactions)
        if frame.empty:
            return []
        frame["week"] = pd.to_datetime(frame["timestamp"]).dt.to_period("W").astype(str)
        weekly = frame.groupby(["category", "week"])["amount"].sum().reset_index()
        anomalies: list[str] = []
        for category, rows in weekly.groupby("category"):
            quartiles = rows["amount"].quantile([0.25, 0.75])
            upper = quartiles[0.75] + 1.5 * (quartiles[0.75] - quartiles[0.25])
            if (rows["amount"] > upper).any():
                anomalies.append(f"{category} has unusually high weekly spending.")
        return anomalies

    def budget_warnings(self, transactions: list[Transaction],
                        year: int, month: int) -> list[str]:
        """Warn when monthly category budgets reach 80 or 100 percent."""
        frame = self.frame(transactions)
        if frame.empty:
            return []
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        monthly = frame[(frame["timestamp"].dt.year == year) &
                        (frame["timestamp"].dt.month == month)]
        warnings: list[str] = []
        for category, limit in self.budgets.items():
            spent = float(monthly.loc[monthly["category"] == category, "amount"].sum())
            ratio = spent / limit if limit else 0.0
            if ratio >= 1.0:
                warnings.append(f"{category}: £{spent:.2f} spent, over the £{limit:.2f} budget.")
            elif ratio >= 0.80:
                warnings.append(f"{category}: £{spent:.2f} spent, 80% of your £{limit:.2f} budget.")
        return warnings

    def takeaway_trend(self, transactions: list[Transaction]) -> str:
        """Compare takeaway spend in the last two calendar months."""
        frame = self.frame(transactions)
        if frame.empty:
            return "No takeaway spending is available yet."
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        months = sorted(frame["timestamp"].dt.to_period("M").unique())
        if len(months) < 2:
            return "Not enough months to measure a takeaway trend."
        previous, latest = months[-2], months[-1]
        previous_spend = float(frame[(frame["timestamp"].dt.to_period("M") == previous) &
                                     (frame["category"] == "Takeaways")]["amount"].sum())
        latest_spend = float(frame[(frame["timestamp"].dt.to_period("M") == latest) &
                                   (frame["category"] == "Takeaways")]["amount"].sum())
        if previous_spend == 0:
            return "Takeaway spending increased, with no spending in the previous month."
        increase = ((latest_spend - previous_spend) / previous_spend) * 100
        return f"Takeaway spending changed by {increase:.0f}% in the latest month."

    def savings_suggestions(self, transactions: list[Transaction]) -> list[dict[str, object]]:
        """Create concrete takeaway and subscription suggestions."""
        frame = self.frame(transactions)
        suggestions: list[dict[str, object]] = []
        if not frame.empty:
            takeaways = frame[frame["category"] == "Takeaways"]["amount"].sum()
            if takeaways > 0:
                suggestions.append({
                    "title": "Cut two takeaway orders",
                    "explanation": "Two fewer takeaway orders a week could reduce monthly spend.",
                    "estimated_monthly_saving": round(takeaways / 4.0, 2),
                })
        return suggestions

    def subscription_suggestions(self, transactions: list[Transaction]) -> list[str]:
        """Detect merchants repeated in at least three months."""
        frame = self.frame(transactions)
        if frame.empty:
            return []
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        frame["month"] = frame["timestamp"].dt.to_period("M").astype(str)
        repeated = frame.groupby(["merchant_clean", "month"]).size().groupby("merchant_clean").size()
        return [merchant for merchant, months in repeated.items() if months >= 3]

    def store_actions(self, title: str, explanation: str,
                      estimated_monthly_saving: float) -> int | None:
        """Store an insight and return its ID."""
        if self.engine is None:
            return None
        with Session(self.engine) as session:
            result = session.execute(insert(insights_table).values(
                title=title,
                explanation=explanation,
                estimated_monthly_saving=estimated_monthly_saving,
                status="PENDING",
            ))
            session.commit()
            return int(result.inserted_primary_key[0])

    def set_action_status(self, insight_id: int, status: str) -> None:
        """Accept or dismiss a stored insight."""
        if self.engine is None:
            return
        if status not in {"ACCEPTED", "DISMISSED"}:
            raise ValueError("Status must be ACCEPTED or DISMISSED")
        with Session(self.engine) as session:
            session.execute(update(insights_table).where(
                insights_table.c.id == insight_id
            ).values(status=status))
            session.commit()

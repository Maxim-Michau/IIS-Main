"""Spend insight and recommendation engine."""

from datetime import datetime
from typing import Iterable
import pandas as pd
from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from expense_ai.models.transaction import Transaction
from expense_ai.storage.database import insights_table
from config.settings import TAKEAWAY_ORDERS_REDUCED_PER_WEEK, WEEKS_PER_MONTH_ESTIMATE


def monthly_category_spending(
    transactions: list[Transaction], month: str
) -> dict[str, float]:
    """Return category totals for one YYYY-MM month."""
    totals: dict[str, float] = {}
    for transaction in transactions:
        if transaction.timestamp.strftime("%Y-%m") == month:
            totals[transaction.category] = (
                totals.get(transaction.category, 0.0) + transaction.amount
            )
    return totals


class InsightEngine:
    """Calculate anomalies, trends, budgets and savings ideas."""

    def __init__(self, budgets: dict[str, float] | None = None,
                 engine: Engine | None = None,
                 now: datetime | None = None) -> None:
        """Configure category budgets."""
        self.budgets = budgets or {}
        self.engine = engine
        self.now = now or datetime.now()

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
        monthly = monthly_category_spending(
            transactions, f"{year:04d}-{month:02d}"
        )
        warnings: list[str] = []
        for category, limit in self.budgets.items():
            spent = monthly.get(category, 0.0)
            if limit == 0:
                if spent > 0:
                    warnings.append(
                        f"{category}: £{spent:.2f} spent against a £0.00 budget."
                    )
                continue
            ratio = spent / limit
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
        frame["period"] = frame["timestamp"].dt.to_period("M")
        current_period = pd.Period(self.now, freq="M")
        complete_months = sorted(
            period for period in frame["period"].unique()
            if period < current_period
        )
        if len(complete_months) < 2:
            return "Not enough months to measure a takeaway trend."
        previous, latest = complete_months[-2:]
        previous_spend = float(frame[(frame["timestamp"].dt.to_period("M") == previous) &
                                     (frame["category"] == "Takeaways")]["amount"].sum())
        latest_spend = float(frame[(frame["timestamp"].dt.to_period("M") == latest) &
                                   (frame["category"] == "Takeaways")]["amount"].sum())
        partial_label = (
            f" {self.now.strftime('%B %Y')} is partial and excluded."
            if (frame["period"] == current_period).any() else ""
        )
        if previous_spend == 0:
            return (
                f"Takeaway spending increased from no spending in {previous} to "
                f"£{latest_spend:.2f} in {latest}.{partial_label}"
            )
        increase = ((latest_spend - previous_spend) / previous_spend) * 100
        return (
            f"Takeaway spending changed by {increase:.0f}% from {previous} to "
            f"{latest}.{partial_label}"
        )

    def savings_suggestions(self, transactions: list[Transaction]) -> list[dict[str, object]]:
        """Create concrete takeaway and subscription suggestions."""
        frame = self.frame(transactions)
        suggestions: list[dict[str, object]] = []
        if not frame.empty:
            takeaway_rows = frame[frame["category"] == "Takeaways"]
            total_spend = float(takeaway_rows["amount"].sum())
            months = takeaway_rows["timestamp"].map(
                lambda value: pd.Timestamp(value).to_period("M")
            ).nunique()
            order_count = len(takeaway_rows)
            if total_spend > 0 and months > 0 and order_count > 0:
                average_monthly_spend = total_spend / months
                average_order_value = total_spend / order_count
                orders_reduced = (
                    TAKEAWAY_ORDERS_REDUCED_PER_WEEK * WEEKS_PER_MONTH_ESTIMATE
                )
                saving = orders_reduced * average_order_value
                suggestions.append({
                    "title": "Cut two takeaway orders",
                    "explanation": (
                        f"Average takeaway spend is £{average_monthly_spend:.2f} per "
                        f"observed month across {months} months. Average order value "
                        f"is £{average_order_value:.2f} across {order_count} orders. "
                        f"Formula: {TAKEAWAY_ORDERS_REDUCED_PER_WEEK} fewer orders/week "
                        f"× {WEEKS_PER_MONTH_ESTIMATE} weeks/month = {orders_reduced} "
                        f"orders × "
                        f"£{average_order_value:.2f} = about £{saving:.2f}/month."
                    ),
                    "estimated_monthly_saving": round(saving, 2),
                })
        return suggestions

    def subscription_suggestions(self, transactions: list[Transaction]) -> list[str]:
        """Detect merchants repeated in at least three months."""
        from expense_ai.ai.categorisers.recurrence import RecurrenceDetector

        grouped: dict[str, list[Transaction]] = {}
        for transaction in transactions:
            grouped.setdefault(transaction.merchant_clean, []).append(transaction)
        detector = RecurrenceDetector(self.engine)
        return [
            merchant
            for merchant, history in grouped.items()
            if detector.detect(history[-1], history).is_recurring
        ]

    def store_actions(self, title: str, explanation: str,
                      estimated_monthly_saving: float) -> int | None:
        """Store an insight and return its ID."""
        if self.engine is None:
            return None
        with Session(self.engine) as session:
            existing = session.execute(select(insights_table).where(
                insights_table.c.title == title
            ).limit(1)).mappings().first()
            if existing:
                session.execute(update(insights_table).where(
                    insights_table.c.id == existing["id"]
                ).values(
                    explanation=explanation,
                    estimated_monthly_saving=estimated_monthly_saving,
                ))
                session.commit()
                return int(existing["id"])
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

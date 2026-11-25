"""Feature-based categorisation using transaction context and user history."""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from expense_ai.ai.categorisers.base import Categoriser
from expense_ai.models.transaction import Prediction, Transaction
from expense_ai.storage.database import transactions_table


MCC_CATEGORIES = {
    "5411": "Groceries",
    "5812": "Eating Out",
    "5814": "Takeaways",
    "4111": "Transport",
    "4900": "Rent & Bills",
    "5816": "Subscriptions",
    "5942": "Education",
    "7997": "Health & Fitness",
    "5941": "Shopping",
}


class ContextCategoriser(Categoriser):
    """Combine merchant MCC, time, weekday, amount, and location signals."""

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine

    def categorise(self, transaction: Transaction) -> Prediction:
        scores: dict[str, float] = defaultdict(float)
        evidence: dict[str, list[str]] = defaultdict(list)

        mcc_category = MCC_CATEGORIES.get(transaction.mcc or "")
        if mcc_category:
            scores[mcc_category] += 0.38
            evidence[mcc_category].append("simulated bank MCC")

        if transaction.mcc in {"5812", "5814"} and (
            transaction.timestamp.hour >= 21 or transaction.timestamp.hour < 5
        ):
            scores["Takeaways"] += 0.16
            evidence["Takeaways"].append("late-night food purchase")

        history = self._confirmed_history()
        features = self._features(transaction)
        weights = {"location": 0.10, "time": 0.12, "weekday": 0.08, "amount": 0.10, "mcc": 0.20}
        for row in history:
            previous_features = self._features(row)
            category = row.category
            for feature, weight in weights.items():
                if features[feature] is not None and features[feature] == previous_features[feature]:
                    scores[category] += weight
                    evidence[category].append(f"matching {feature}")

        if not scores:
            return Prediction("Other", 0.20, "No contextual signals matched.", "CONTEXT")
        category, score = max(scores.items(), key=lambda item: item[1])
        confidence = min(0.82, 0.20 + score)
        details = ", ".join(dict.fromkeys(evidence[category]))
        return Prediction(category, confidence, f"Context signals: {details}.", "CONTEXT")

    def _confirmed_history(self) -> list[Transaction]:
        if self.engine is None:
            return []
        with Session(self.engine) as session:
            rows = session.execute(
                select(transactions_table).where(
                    transactions_table.c.status.in_(("CONFIRMED", "CORRECTED"))
                )
            ).mappings().all()
        return [Transaction(**dict(row)) for row in rows]

    @staticmethod
    def _features(transaction: Transaction) -> dict[str, object]:
        hour = transaction.timestamp.hour
        time_band = "late" if hour >= 21 or hour < 5 else "morning" if hour < 12 else "afternoon"
        return {
            "location": transaction.location,
            "time": time_band,
            "weekday": "weekend" if transaction.timestamp.weekday() >= 5 else "weekday",
            "amount": "small" if transaction.amount < 10 else "medium" if transaction.amount < 50 else "large",
            "mcc": transaction.mcc,
        }

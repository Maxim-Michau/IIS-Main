"""Fuzzy matching against merchants the user has confirmed."""

from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from expense_ai.ai.categorisers.base import Categoriser
from expense_ai.models.transaction import Prediction, Transaction
from expense_ai.storage.database import transactions_table


class FuzzyMerchantCategoriser(Categoriser):
    """Reuse a user's confirmed label for a similar merchant string."""

    def __init__(self, engine: Engine | None = None, threshold: float = 0.72) -> None:
        self.engine = engine
        self.threshold = threshold

    def categorise(self, transaction: Transaction) -> Prediction:
        if self.engine is None:
            return Prediction("Other", 0.20, "No confirmed merchant history is available.", "FUZZY")
        with Session(self.engine) as session:
            rows = session.execute(
                select(transactions_table.c.merchant_clean, transactions_table.c.category)
                .where(transactions_table.c.status.in_(("CONFIRMED", "CORRECTED")))
            ).all()
        merchant = self._normalise(transaction.merchant_clean or transaction.merchant_raw)
        matches = [
            (SequenceMatcher(None, merchant, self._normalise(name)).ratio(), category)
            for name, category in rows
            if name
        ]
        if not matches:
            return Prediction("Other", 0.20, "No confirmed merchant history is available.", "FUZZY")
        similarity, category = max(matches, key=lambda match: match[0])
        if similarity < self.threshold:
            return Prediction("Other", 0.20, "No confirmed merchant is similar enough.", "FUZZY")
        confidence = min(0.94, 0.70 + (similarity - self.threshold) * 0.8)
        return Prediction(
            category,
            confidence,
            f"Similar to a merchant you confirmed ({similarity:.0%} match).",
            "FUZZY",
        )

    @staticmethod
    def _normalise(value: str) -> str:
        return " ".join(value.casefold().split())

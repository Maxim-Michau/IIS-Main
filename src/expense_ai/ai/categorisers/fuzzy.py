"""Fuzzy matching against merchants the user has confirmed."""

from difflib import SequenceMatcher

from sqlalchemy import func, select
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
        self._merchant_cache: list[tuple[str, str]] | None = None

    def begin_batch(self) -> None:
        """Cache one confirmed category per merchant for an ingestion batch."""
        self._merchant_cache = self._query_confirmed_merchants()

    def end_batch(self) -> None:
        """Release merchant history cached for the completed ingestion batch."""
        self._merchant_cache = None

    def categorise(self, transaction: Transaction) -> Prediction:
        if self.engine is None:
            return Prediction("Other", 0.20, "No confirmed merchant history is available.", "FUZZY")
        merchant = self._normalise(transaction.merchant_clean or transaction.merchant_raw)
        matches = [
            (SequenceMatcher(None, merchant, self._normalise(name)).ratio(), category)
            for name, category in self._confirmed_merchants()
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

    def _confirmed_merchants(self) -> list[tuple[str, str]]:
        if self._merchant_cache is not None:
            return self._merchant_cache
        return self._query_confirmed_merchants()

    def _query_confirmed_merchants(self) -> list[tuple[str, str]]:
        """Load a single confirmed category for each merchant."""
        if self.engine is None:
            return []
        with Session(self.engine) as session:
            rows = session.execute(
                select(
                    transactions_table.c.merchant_clean,
                    transactions_table.c.category,
                    func.count().label("confirmed_count"),
                )
                .where(transactions_table.c.status.in_(("CONFIRMED", "CORRECTED")))
                .group_by(
                    transactions_table.c.merchant_clean,
                    transactions_table.c.category,
                )
                .order_by(
                    transactions_table.c.merchant_clean,
                    func.count().desc(),
                    transactions_table.c.category,
                )
            ).all()
        categories_by_merchant: dict[str, str] = {}
        for name, category, _ in rows:
            categories_by_merchant.setdefault(name, category)
        return list(categories_by_merchant.items())

"""Categoriser interfaces."""

from abc import ABC, abstractmethod
from expense_ai.models.transaction import Transaction
from expense_ai.models.transaction import Prediction


class Categoriser(ABC):
    """Produce a category prediction for a transaction."""

    @abstractmethod
    def categorise(self, transaction: Transaction) -> Prediction:
        """Categorise one transaction."""

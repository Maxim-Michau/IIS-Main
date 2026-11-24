"""Abstract bank data source."""

from abc import ABC, abstractmethod
from typing import Iterable
from expense_ai.models.transaction import Transaction


class BankSource(ABC):
    """Retrieve transactions from an external or synthetic source."""

    @abstractmethod
    def fetch_transactions(self) -> Iterable[Transaction]:
        """Return transactions supplied by this source."""

"""Deliberately unimplemented Open Banking source."""

from typing import Iterable
from expense_ai.models.transaction import Transaction
from expense_ai.sources.bank_source import BankSource


class OpenBankingSource(BankSource):
    """Planned extension; deliberately disabled for security reasons.

    Direct bank connections are not implemented because this project uses
    synthetic or locally supplied CSV data only.
    """

    def fetch_transactions(self) -> Iterable[Transaction]:
        """Raise to prevent accidental real-bank connections."""
        raise NotImplementedError("Open Banking is a planned, unimplemented extension.")

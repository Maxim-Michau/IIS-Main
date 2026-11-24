"""Tests for transaction persistence."""

from datetime import datetime
from expense_ai.models.transaction import Transaction
from expense_ai.storage.repository import TransactionRepository


def test_transaction_crud(engine) -> None:
    """Repository supports create, read, update and delete."""
    repository = TransactionRepository(engine)
    transaction = Transaction(
        id=None,
        timestamp=datetime(2026, 1, 1, 12),
        amount=12.50,
        merchant_raw="TESCO STORES",
        merchant_clean="tesco",
        location="Birmingham",
    )
    created = repository.add(transaction)
    assert created.id is not None
    assert repository.get(created.id).merchant_clean == "tesco"
    created.category = "Groceries"
    repository.update(created)
    assert repository.get(created.id).category == "Groceries"
    assert repository.delete(created.id)
    assert repository.get(created.id) is None

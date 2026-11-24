"""Tests for the offline advisor."""

from datetime import datetime
from expense_ai.models.transaction import Transaction
from expense_ai.ai.advisor import Advisor


def test_advisor_offline_answer() -> None:
    """Offline advisor answers with transaction totals."""
    transactions = [
        Transaction(None, datetime.now(), 25.0, "Tesco", "Tesco", "Birmingham",
                    "Groceries"),
        Transaction(None, datetime.now(), 15.0, "Uber Eats", "Uber Eats", "Birmingham",
                    "Takeaways"),
    ]
    answer = Advisor(transactions).answer("How much did I spend on food?")
    assert "£40.00" in answer

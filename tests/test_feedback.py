"""Tests for feedback learning and undo."""

from datetime import datetime
from expense_ai.models.transaction import Transaction
from expense_ai.ai.feedback import FeedbackLearner


def test_rule_promotion_and_undo(engine) -> None:
    """Repeated answers promote rules and corrections can be undone."""
    learner = FeedbackLearner(engine, promotion_count=2)
    transaction = Transaction(None, datetime.now(), 12.0, "PAYPAL *UNKNOWN", "paypal unknown",
                              "Birmingham")
    transaction.id = 1
    learner.record_answer(transaction, "Shopping", "Groceries")
    transaction.id = 2
    promoted = learner.record_answer(transaction, "Shopping", "Groceries")
    assert promoted
    learner.undo_correction(transaction, "Shopping")
    assert transaction.category == "Shopping"

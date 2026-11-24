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


def test_retraining_threshold_and_metrics(engine) -> None:
    """Feedback threshold and learning metrics are measurable."""
    learner = FeedbackLearner(engine, promotion_count=10, retrain_count=2)
    one = Transaction(None, datetime.now(), 10.0, "A", "A", "Birmingham")
    one.id = 1
    learner.record_answer(one, "Shopping", "Shopping")
    assert not learner.should_retrain()
    two = Transaction(None, datetime.now(), 10.0, "B", "B", "Birmingham")
    two.id = 2
    learner.record_answer(two, "Shopping", "Groceries")
    assert learner.should_retrain()
    assert learner.metrics()["feedback_rows"] == 2

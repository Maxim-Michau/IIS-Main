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


def test_rent_unknown_category_and_month_filters() -> None:
    """Advisor supports Rent & Bills, unknown categories and named months."""
    transactions = [
        Transaction(None, datetime(2026, 10, 5), 650.0, "Rent", "Rent",
                    "Birmingham", "Rent & Bills"),
        Transaction(None, datetime(2026, 10, 10), 25.0, "Tesco", "Tesco",
                    "Birmingham", "Groceries"),
        Transaction(None, datetime(2026, 9, 10), 10.0, "Tesco", "Tesco",
                    "Birmingham", "Groceries"),
    ]
    advisor = Advisor(transactions)
    assert "£650.00" in advisor.answer("How much did I spend on rent?")
    assert "October" not in advisor.answer("How much did I spend on October?")
    assert "don't recognise" in advisor.answer("How much did I spend on antiques?")
    assert "£675.00" in advisor.answer("How much did I spend in October?")


def test_advisor_llm_mock_stays_grounded() -> None:
    """A mocked LLM adapter receives repository-grounded text and can fail safely."""
    transactions = [
        Transaction(None, datetime(2026, 10, 5), 650.0, "Rent", "Rent",
                    "Birmingham", "Rent & Bills"),
    ]
    class Tool:
        @staticmethod
        def answer(question: str, grounded_answer: str) -> str:
            return grounded_answer
    class MockLLM:
        tools = Tool()
    assert "£650.00" in Advisor(transactions, MockLLM()).answer_with_llm(
        "How much did I spend on rent?"
    )

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


def test_chart_for_monthly_category_and_merchant_questions() -> None:
    """Charts use named month data and match category or merchant intent."""
    transactions = [
        Transaction(None, datetime(2026, 10, 5), 10.0, "Takeout A", "Takeout A",
                    "Birmingham", "Takeaways"),
        Transaction(None, datetime(2026, 10, 8), 20.0, "Tesco", "Tesco",
                    "Birmingham", "Groceries"),
        Transaction(None, datetime(2026, 11, 5), 15.0, "Takeout A", "Takeout A",
                    "Birmingham", "Takeaways"),
    ]
    advisor = Advisor(transactions)

    category_chart = advisor.chart_for("How much did I spend on Takeaways by month?")
    merchant_chart = advisor.chart_for("Show top merchants")
    monthly_chart = advisor.chart_for("Show spending by month")

    assert category_chart is not None
    assert category_chart.layout.title.text == "Takeaways spending by month"
    assert list(category_chart.data[0].x) == ["2026-10", "2026-11"]
    assert list(category_chart.data[0].y) == [10.0, 15.0]
    assert merchant_chart is not None
    assert merchant_chart.layout.title.text == "Top merchants"
    assert monthly_chart is not None
    assert list(monthly_chart.data[0].x) == ["2026-10", "2026-11"]

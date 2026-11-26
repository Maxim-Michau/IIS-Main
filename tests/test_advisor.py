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
    advisor = Advisor(transactions, now=datetime(2026, 11, 26))
    assert "£650.00" in advisor.answer("How much did I spend on rent?")
    assert "October" not in advisor.answer("How much did I spend on October?")
    assert "don't recognise" in advisor.answer("How much did I spend on antiques?")
    assert "£675.00" in advisor.answer("How much did I spend in October?")


def test_advisor_uses_word_boundaries_and_resolves_named_months() -> None:
    """Merchant/category terms are bounded and named months choose the latest data."""
    transactions = [
        Transaction(None, datetime(2025, 10, 5), 10.0, "Rent", "Rent",
                    "Birmingham", "Rent & Bills"),
        Transaction(None, datetime(2026, 9, 5), 20.0, "Tesco", "Tesco",
                    "Birmingham", "Groceries"),
        Transaction(None, datetime(2026, 10, 5), 30.0, "Tesco", "Tesco",
                    "Birmingham", "Groceries"),
        Transaction(None, datetime(2026, 10, 8), 40.0, "Rail", "Rail",
                    "Birmingham", "Transport"),
        Transaction(None, datetime(2026, 11, 5), 50.0, "Tesco", "Tesco",
                    "Birmingham", "Groceries"),
    ]
    advisor = Advisor(transactions, now=datetime(2026, 11, 15))

    assert "£70.00" in advisor.answer("How much did I spend in October?")
    assert "£10.00" in advisor.answer("How much did I spend in October 2025?")
    assert "£100.00" in advisor.answer("How much on Tesco?")
    assert "don't recognise 'current account'" in advisor.answer(
        "How much did I spend on current account?"
    )
    assert "November 2026 is partial" in advisor.answer("How much in November?")


def test_advisor_month_comparison_and_why_explain_categories_in_gbp() -> None:
    """Complete-month comparisons exclude a partial month and explain category deltas."""
    transactions = [
        Transaction(None, datetime(2026, 9, 5), 100.0, "A", "A", None, "Groceries"),
        Transaction(None, datetime(2026, 9, 8), 50.0, "B", "B", None, "Transport"),
        Transaction(None, datetime(2026, 10, 5), 150.0, "A", "A", None, "Groceries"),
        Transaction(None, datetime(2026, 10, 8), 50.0, "B", "B", None, "Transport"),
        Transaction(None, datetime(2026, 11, 5), 900.0, "C", "C", None, "Shopping"),
    ]
    advisor = Advisor(transactions, now=datetime(2026, 11, 15))

    comparison = advisor.answer("Compare my months")
    explanation = advisor.answer("Why was October expensive?")

    assert "October 2026 spending was £200.00" in comparison
    assert "September 2026 spending was £150.00" in comparison
    assert "November 2026 is partial and excluded" in comparison
    assert "Groceries +£50.00" in explanation
    assert "October 2026 compared with September 2026" in explanation


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

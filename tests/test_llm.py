"""Tests for optional LLM categorisation."""

from datetime import datetime
from expense_ai.ai.categorisers.llm import LLMCategoriser
from expense_ai.models.transaction import Transaction


class MockClient:
    """Minimal mocked Anthropic client."""

    class Messages:
        """Minimal messages API."""

        @staticmethod
        def create(**kwargs):
            """Return structured mock JSON."""
            class Block:
                text = '{"category": "Groceries", "confidence": 0.90, "reason": "Food shop"}'
            class Response:
                content = [Block()]
            return Response()

    messages = Messages()


def test_llm_structured_mock() -> None:
    """Mocked LLM returns a validated prediction."""
    categoriser = LLMCategoriser(enabled=True, client=MockClient())
    prediction = categoriser.categorise(
        Transaction(None, datetime.now(), 10.0, "TESCO", "tesco", "Birmingham")
    )
    assert prediction.category == "Groceries"
    assert prediction.confidence_score == 0.90

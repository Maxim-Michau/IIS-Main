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


def test_llm_extracts_fenced_json_and_retries_once(monkeypatch) -> None:
    """Fenced JSON is accepted and a single failed request is retried."""
    class RetryClient:
        def __init__(self) -> None:
            self.calls = 0
            self.models = []

        class Messages:
            def __init__(self, owner: "RetryClient") -> None:
                self.owner = owner

            def create(self, **kwargs):
                self.owner.calls += 1
                self.owner.models.append(kwargs["model"])
                if self.owner.calls == 1:
                    raise RuntimeError("temporary error")

                class Block:
                    text = (
                        'Result:\n```json\n{"category":"Travel",'
                        '"confidence":0.8,"reason":"Trip"}\n```'
                    )

                class Response:
                    content = [Block()]

                return Response()

        @property
        def messages(self):
            return self.Messages(self)

    client = RetryClient()
    monkeypatch.setenv("ANTHROPIC_MODEL", "test-model")
    categoriser = LLMCategoriser(enabled=True, client=client)
    prediction = categoriser.categorise(
        Transaction(None, datetime.now(), 10.0, "TRAIN", "Train", "London")
    )

    assert prediction.category == "Travel"
    assert client.calls == 2
    assert client.models == ["test-model", "test-model"]

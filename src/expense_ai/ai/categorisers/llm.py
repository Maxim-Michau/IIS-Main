"""Optional Anthropic LLM categoriser."""

import json
import os
from typing import Any
from expense_ai.models.transaction import Prediction, Transaction
from expense_ai.ai.categorisers.base import Categoriser


class LLMCategoriser(Categoriser):
    """Clean and classify merchants through a structured Anthropic JSON response."""

    CATEGORIES = ["Groceries", "Eating Out", "Takeaways", "Transport", "Rent & Bills",
                  "Subscriptions", "Shopping", "Entertainment", "Education",
                  "Health & Fitness", "Travel", "Other"]

    def __init__(self, enabled: bool = False, client: Any | None = None) -> None:
        """Configure optional LLM use."""
        self.enabled = enabled
        self.client = client

    def categorise(self, transaction: Transaction) -> Prediction:
        """Return a validated prediction, or a safe low-confidence fallback."""
        if not self.enabled:
            return Prediction("Other", 0.20, "LLM categorisation is disabled.", "LLM")
        try:
            if self.client is None:
                import anthropic
                if not os.getenv("ANTHROPIC_API_KEY"):
                    raise RuntimeError("No Anthropic API key")
                self.client = anthropic.Anthropic()
            prompt = ("Clean this merchant and choose exactly one category from " +
                      ", ".join(self.CATEGORIES) +
                      f". Merchant: {transaction.merchant_raw}. Return JSON with category, "
                      "confidence, reason.")
            response = self.client.messages.create(
                model="claude-3-5-haiku-latest",
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}],
            )
            return self._parse(response.content[0].text)
        except Exception:
            return Prediction("Other", 0.20, "LLM unavailable; offline rules remain in use.", "LLM")

    def _parse(self, text: str) -> Prediction:
        """Parse and validate structured JSON, retrying once is managed by callers."""
        data = json.loads(text)
        category = data["category"]
        confidence = float(data["confidence"])
        reason = str(data["reason"])
        if category not in self.CATEGORIES or not 0 <= confidence <= 1:
            raise ValueError("Invalid LLM prediction")
        return Prediction(category, confidence, reason, "LLM")

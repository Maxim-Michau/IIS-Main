"""Optional Anthropic LLM categoriser."""

import json
import logging
import os
import re
from typing import Any
from expense_ai.models.transaction import Prediction, Transaction
from expense_ai.ai.categorisers.base import Categoriser

logger = logging.getLogger(__name__)


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
        for attempt in range(2):
            try:
                self._ensure_client()
                prompt = (
                    "Clean this merchant and choose exactly one category from "
                    + ", ".join(self.CATEGORIES)
                    + f". Merchant: {transaction.merchant_raw}. Return JSON with category, "
                    "confidence, reason."
                )
                response = self.client.messages.create(
                    model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5"),
                    max_tokens=150,
                    messages=[{"role": "user", "content": prompt}],
                )
                return self._parse(response.content[0].text)
            except Exception:
                logger.exception("LLM categorisation attempt %s failed", attempt + 1)
        return Prediction(
            "Other", 0.20, "LLM unavailable; offline rules remain in use.", "LLM"
        )

    def _ensure_client(self) -> None:
        """Create the Anthropic client only when an API key is configured."""
        if self.client is not None:
            return
        import anthropic

        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError("No Anthropic API key")
        self.client = anthropic.Anthropic()

    def _parse(self, text: str) -> Prediction:
        """Extract and validate one JSON object from model output."""
        cleaned = re.sub(
            r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.IGNORECASE
        )
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match is None:
            raise ValueError("LLM response did not contain a JSON object")
        data = json.loads(match.group())
        category = data["category"]
        confidence = float(data["confidence"])
        reason = str(data["reason"])
        if category not in self.CATEGORIES or not 0 <= confidence <= 1:
            raise ValueError("Invalid LLM prediction")
        return Prediction(category, confidence, reason, "LLM")

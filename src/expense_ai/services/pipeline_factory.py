"""Categorisation pipeline construction."""

import os

from config import settings
from expense_ai.ai.categorisers.llm import LLMCategoriser
from expense_ai.ai.categorisers.ml import MLCategoriser
from expense_ai.ai.categorisers.rule import RuleCategoriser
from expense_ai.ai.categorisers.context import ContextCategoriser
from expense_ai.ai.categorisers.fuzzy import FuzzyMerchantCategoriser
from expense_ai.ai.categorisers.recurrence import RecurrenceDetector
from expense_ai.ai.pipeline import CategorisationPipeline


def build_pipeline(settings_module: object = settings) -> CategorisationPipeline:
    """Build rule, persisted ML, and optional LLM categorisers."""
    categorisers = [
        RuleCategoriser(),
        FuzzyMerchantCategoriser(),
        ContextCategoriser(),
        RecurrenceDetector(),
    ]
    ml = MLCategoriser(getattr(settings_module, "MODEL_PATH", settings.MODEL_PATH))
    if ml.is_trained():
        categorisers.append(ml)
    llm_enabled = bool(
        getattr(settings_module, "USE_LLM", False)
        and os.getenv("ANTHROPIC_API_KEY")
    )
    if llm_enabled:
        categorisers.append(LLMCategoriser(enabled=True))
    return CategorisationPipeline(categorisers)

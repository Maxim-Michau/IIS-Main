"""Transaction and categorisation result models."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Transaction:
    """A bank transaction."""

    id: Optional[int]
    timestamp: datetime
    amount: float
    merchant_raw: str
    merchant_clean: str
    location: Optional[str]
    category: str = "Other"
    confidence_score: float = 0.0
    status: str = "TENTATIVE"
    explanation: str = ""
    source: str = "SYNTHETIC"
    true_category: Optional[str] = None
    method: str = "RULE"
    is_recurring: bool = False
    note: Optional[str] = None
    mcc: Optional[str] = None


@dataclass
class Prediction:
    """A categorisation prediction."""

    category: str
    confidence_score: float
    explanation: str
    method: str

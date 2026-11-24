"""Insight model."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Insight:
    """A recommendation or spending insight."""

    id: Optional[int]
    title: str
    explanation: str
    estimated_monthly_saving: float
    status: str = "PENDING"

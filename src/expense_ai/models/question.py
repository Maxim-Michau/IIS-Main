"""User clarification question model."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Question:
    """A clarifying question for a transaction."""

    id: Optional[int]
    transaction_id: int
    question_type: str
    prompt_text: str
    options: str
    status: str = "PENDING"
    answer: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    answered_at: Optional[datetime] = None
    surfaced_at: Optional[datetime] = None

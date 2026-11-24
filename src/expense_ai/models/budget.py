"""Budget model."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Budget:
    """A monthly category spending limit."""

    id: Optional[int]
    category: str
    monthly_limit: float

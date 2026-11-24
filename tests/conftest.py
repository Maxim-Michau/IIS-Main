"""Shared pytest fixtures."""

import pytest
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine
from expense_ai.storage.database import create_database


@pytest.fixture
def engine():
    """Create an isolated in-memory database."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from expense_ai.storage.database import metadata
    metadata.create_all(engine)
    return engine

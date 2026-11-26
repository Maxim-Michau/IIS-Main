"""Tests for the synthetic data generation command."""

from datetime import datetime

import pytest

from expense_ai.ai.pipeline import CategorisationPipeline
from expense_ai.models.transaction import Transaction
from expense_ai.storage.database import transactions_table
from scripts import generate_data
from sqlalchemy import select
from sqlalchemy.orm import Session


def test_generator_refuses_duplicates_and_reset_replaces_data(
    engine, monkeypatch, tmp_path
) -> None:
    """Generation refuses populated databases unless reset was explicitly requested."""
    monkeypatch.setattr(generate_data, "create_database", lambda: engine)
    monkeypatch.setattr(
        generate_data, "build_pipeline", lambda: CategorisationPipeline([])
    )
    monkeypatch.setattr(
        generate_data.SyntheticBankSource,
        "fetch_transactions",
        lambda self: [
            Transaction(
                None, datetime(2026, 11, 1), 12.0, "TESCO", "Tesco",
                "Cambridge", true_category="Groceries",
            )
        ],
    )
    model_path = tmp_path / "categoriser.joblib"
    monkeypatch.setattr("config.settings.MODEL_PATH", model_path)

    assert generate_data.generate_data() == 1
    with pytest.raises(ValueError, match="pass --reset"):
        generate_data.generate_data()
    model_path.write_bytes(b"old model")

    assert generate_data.generate_data(reset=True) == 1

    with Session(engine) as session:
        rows = session.execute(select(transactions_table)).all()
    assert len(rows) == 1
    assert not model_path.exists()

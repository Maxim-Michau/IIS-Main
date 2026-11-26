"""Seeded Streamlit app smoke tests."""

import importlib
from datetime import datetime
from collections.abc import Iterator

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from config import settings
from expense_ai.ai.pipeline import CategorisationPipeline
from expense_ai.models.transaction import Transaction
from expense_ai.services.app_service import AppService
from expense_ai.storage.database import create_database
from expense_ai.storage.database import metadata
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from expense_ai.storage.database import questions_table


APP_PATH = "src/expense_ai/ui/app.py"


@pytest.fixture
def seeded_app_database(
    monkeypatch, tmp_path
) -> Iterator[tuple[AppService, int]]:
    """Point the app at a temporary database seeded with real view data."""
    original_database_url = settings.DATABASE_URL
    database_url = f"sqlite:///{(tmp_path / 'nested' / 'app.db').as_posix()}"
    monkeypatch.setenv("EXPENSE_AI_DATABASE_URL", database_url)
    importlib.reload(settings)
    assert settings.DATABASE_URL == database_url
    monkeypatch.setattr(settings, "MODEL_PATH", tmp_path / "model.joblib")

    engine = create_database(settings.DATABASE_URL)
    service = AppService(engine, CategorisationPipeline([]))
    service.repository.add(Transaction(
        None, datetime(2026, 10, 1, 12), 10.0, "UNKNOWN SHOP", "Unknown Shop",
        "Cambridge", category="Other", status="CONFIRMED",
    ))
    target = service.repository.add(Transaction(
        None, datetime(2026, 11, 1, 12), 12.0, "UNKNOWN SHOP", "Unknown Shop",
        "Wellington", category="Other", status="TENTATIVE",
    ))
    service.repository.add(Transaction(
        None, datetime(2026, 11, 2, 12), 25.0, "CUSTOM MERCHANT",
        "Custom Merchant", "Leeds", category="Custom Category",
        status="CONFIRMED",
    ))
    service.clarification._create_question(
        target, "CATEGORY", "What category is this payment?", ["Groceries", "Other"]
    )
    service.clarification.location_question(target)
    service.clarification.release_questions()
    service.save_budget("Groceries", 100.0, "2026-11")
    st.cache_resource.clear()

    try:
        yield service, target.id
    finally:
        st.cache_resource.clear()
        engine.dispose()
        settings.DATABASE_URL = original_database_url


def test_app_loads_without_exceptions(seeded_app_database) -> None:
    """The dashboard renders against seeded temporary data."""
    app = AppTest.from_file(APP_PATH)
    app.run(timeout=30)
    assert not app.exception


def test_each_view_loads_without_exceptions(seeded_app_database) -> None:
    """Every view renders with seeded transactions and questions."""
    for view in ("Dashboard", "Inbox", "Transactions", "Advisor", "Budgets", "Settings"):
        app = AppTest.from_file(APP_PATH)
        app.run(timeout=30)
        app.radio[0].set_value(view).run(timeout=30)
        assert not app.exception


def test_inbox_category_answer_updates_data_end_to_end(seeded_app_database) -> None:
    """A user can answer a surfaced Inbox question through the rendered app."""
    service, transaction_id = seeded_app_database
    app = AppTest.from_file(APP_PATH)
    app.run(timeout=30)
    app.radio[0].set_value("Inbox").run(timeout=30)

    assert "Custom Category" in app.selectbox[0].options
    answer_button = next(button for button in app.button if button.label == "Groceries")
    answer_button.click().run(timeout=30)

    updated = service.repository.get(transaction_id)
    assert updated.category == "Groceries"
    assert updated.method == "USER"
    assert updated.status == "CORRECTED"
    with Session(service.repository.engine) as session:
        assert session.execute(
            select(questions_table.c.status).where(
                questions_table.c.transaction_id == transaction_id,
                questions_table.c.question_type == "CATEGORY",
            )
        ).scalar_one() == "ANSWERED"
    assert not app.exception


def test_inbox_location_choices_use_the_merchant_history(
    seeded_app_database,
) -> None:
    """Location buttons show the asked merchant's places, not unrelated cities."""
    app = AppTest.from_file(APP_PATH)
    app.run(timeout=30)
    app.radio[0].set_value("Inbox").run(timeout=30)

    labels = [button.label for button in app.button]
    assert "Cambridge" in labels
    assert "Leeds" not in labels
    assert not app.exception


def test_transaction_search_treats_regex_characters_literally(
    seeded_app_database,
) -> None:
    """Searching for regex metacharacters does not crash the Transactions view."""
    app = AppTest.from_file(APP_PATH)
    app.run(timeout=30)
    app.radio[0].set_value("Transactions").run(timeout=30)
    app.text_input[0].set_value("*(").run(timeout=30)

    assert not app.exception


def test_settings_reset_clears_seeded_app_and_reruns(
    seeded_app_database,
) -> None:
    """The Settings reset button clears all app data and returns to the empty state."""
    service, _ = seeded_app_database
    app = AppTest.from_file(APP_PATH)
    app.run(timeout=30)
    app.radio[0].set_value("Settings").run(timeout=30)
    next(button for button in app.button if button.label == "Reset demo data").click().run(
        timeout=30
    )

    assert not app.exception
    assert service.get_transactions() == []
    with Session(service.repository.engine) as session:
        counts = {
            table.name: session.execute(
                select(func.count()).select_from(table)
            ).scalar_one()
            for table in metadata.sorted_tables
        }
    assert all(count == 0 for count in counts.values()), counts

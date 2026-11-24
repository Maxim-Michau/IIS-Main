"""Streamlit app smoke tests."""

from streamlit.testing.v1 import AppTest


APP_PATH = "src/expense_ai/ui/app.py"


def test_app_loads_without_exceptions() -> None:
    """The entry point and default view load cleanly."""
    app = AppTest.from_file(APP_PATH)
    app.run(timeout=30)
    assert not app.exception


def test_each_view_loads_without_exceptions() -> None:
    """Every sidebar view can be selected and rendered."""
    for view in ("Dashboard", "Inbox", "Transactions", "Advisor", "Budgets", "Settings"):
        app = AppTest.from_file(APP_PATH)
        app.run(timeout=30)
        app.radio[0].set_value(view).run(timeout=30)
        assert not app.exception

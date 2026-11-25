"""Expense-ai Streamlit entry point."""

import streamlit as st

from config import settings
from expense_ai.services.app_service import AppService
from expense_ai.services.pipeline_factory import build_pipeline
from expense_ai.storage.database import create_database
from expense_ai.ui.views.advisor import render as render_advisor
from expense_ai.ui.views.budgets import render as render_budgets
from expense_ai.ui.views.dashboard import render as render_dashboard
from expense_ai.ui.views.inbox import render as render_inbox
from expense_ai.ui.views.settings import render as render_settings
from expense_ai.ui.views.transactions import render as render_transactions




@st.cache_resource
def get_service() -> AppService:
    """Create one shared application service per Streamlit process."""
    engine = create_database(settings.DATABASE_URL)
    return AppService(engine, build_pipeline(settings))


st.set_page_config(page_title="expense-ai", page_icon="£", layout="wide")
service = get_service()

pending = service.get_pending_questions()
st.sidebar.title("expense-ai")
st.sidebar.caption("Simulated student finance assistant")
st.sidebar.markdown(f"**Inbox · {len(pending)} pending**")
st.sidebar.radio(
    "Navigation",
    ["Dashboard", "Inbox", "Transactions", "Advisor", "Budgets", "Settings"],
    index=0,
    key="expense_ai_view",
)

transactions = service.get_transactions()
if not transactions:
    st.title("Expense AI")
    st.warning("The database is empty. Generate the reproducible synthetic demo to get started.")
    if st.button("Generate synthetic data"):
        from expense_ai.sources.synthetic import SyntheticBankSource
        service.ingest_all(SyntheticBankSource().fetch_transactions())
        st.cache_resource.clear()
        st.rerun()
else:
    selected = st.session_state.expense_ai_view
    if selected == "Dashboard":
        render_dashboard(service)
    elif selected == "Inbox":
        render_inbox(service)
    elif selected == "Transactions":
        render_transactions(service)
    elif selected == "Advisor":
        render_advisor(service)
    elif selected == "Budgets":
        render_budgets(service)
    else:
        render_settings(service)

"""Expense-ai Streamlit entry point."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st
from config.settings import DATABASE_URL
from expense_ai.storage.database import create_database
from expense_ai.ai.categorisers.rule import RuleCategoriser
from expense_ai.ai.pipeline import CategorisationPipeline
from expense_ai.services.app_service import AppService


st.set_page_config(page_title="expense-ai", page_icon="£", layout="wide")
st.sidebar.title("expense-ai")
st.sidebar.caption("Simulated student finance assistant")
st.sidebar.button("Inbox 🔔")

engine = create_database(DATABASE_URL)
service = AppService(engine, CategorisationPipeline([RuleCategoriser()]))
transactions = service.get_transactions()

st.title("Expense AI")
if not transactions:
    st.info("Generate sample data with `python scripts/generate_data.py`.")
else:
    st.metric("Transactions", len(transactions))
    st.metric("Total spend", f"£{sum(item.amount for item in transactions):,.2f}")

"""Settings view."""

import streamlit as st


def render(service: object) -> None:
    """Render settings and reset/simulation controls."""
    st.header("Settings")
    st.toggle("Use optional LLM", value=False, disabled=True,
              help="Set USE_LLM=true and ANTHROPIC_API_KEY in .env")
    st.slider("Auto-accept threshold", 0.0, 1.0, 0.85)
    st.slider("Question threshold", 0.0, 1.0, 0.50)
    st.slider("Maximum questions per day", 1, 20, 5)
    if st.button("Simulate new transactions arriving"):
        from expense_ai.sources.synthetic import SyntheticBankSource
        sample = next(iter(SyntheticBankSource(seed=99, months=1).fetch_transactions()))
        service.ingest(sample)
        st.success(f"Added simulated {sample.merchant_clean} transaction")
    if st.button("Reset demo data"):
        from sqlalchemy import delete
        from sqlalchemy.orm import Session
        for table in ("transactions", "questions", "feedback", "insights", "merchant_rules"):
            pass
        with Session(service.repository.engine) as session:
            for table_name in (
                "transactions", "questions", "feedback", "insights", "merchant_rules"
            ):
                from expense_ai.storage.database import (
                    transactions_table, questions_table, feedback_table,
                    insights_table, merchant_rules_table,
                )
                table = {
                    "transactions": transactions_table,
                    "questions": questions_table,
                    "feedback": feedback_table,
                    "insights": insights_table,
                    "merchant_rules": merchant_rules_table,
                }[table_name]
                session.execute(delete(table))
            session.commit()
        st.success("Demo data reset")
    if st.button("Simulate new transactions"):
        st.success("Simulated a new transaction; run ingestion to process it.")

"""Settings view."""

import os
import random
from datetime import datetime, timedelta

import streamlit as st


def render(service: object) -> None:
    """Render settings and reset/simulation controls."""
    st.header("Settings")
    from config import settings

    llm_ready = settings.USE_LLM and bool(os.getenv("ANTHROPIC_API_KEY"))
    st.toggle(
        "Use optional LLM",
        value=llm_ready,
        disabled=True,
        help="Configure USE_LLM=true and ANTHROPIC_API_KEY in .env",
    )
    if not llm_ready:
        st.info("LLM unavailable: set USE_LLM=true and ANTHROPIC_API_KEY in .env.")
    else:
        st.success("LLM enabled from environment configuration.")

    auto_threshold = st.slider(
        "Auto-accept threshold",
        0.0,
        1.0,
        float(st.session_state.get("auto_threshold", 0.85)),
    )
    ask_threshold = st.slider(
        "Question threshold",
        0.0,
        1.0,
        float(st.session_state.get("ask_threshold", 0.50)),
    )
    question_cap = st.slider(
        "Maximum questions per day",
        1,
        20,
        int(st.session_state.get("question_cap", 5)),
    )
    st.session_state.auto_threshold = auto_threshold
    st.session_state.ask_threshold = ask_threshold
    st.session_state.question_cap = question_cap
    if auto_threshold <= ask_threshold:
        st.error("Auto-accept threshold must be greater than question threshold.")
    else:
        service.configure_clarification(
            auto_threshold, ask_threshold, question_cap
        )
    st.caption("These values apply to transactions ingested after this setting change.")

    if st.button("Simulate new transactions arriving"):
        from expense_ai.models.transaction import Transaction

        seed = int(datetime.now().timestamp()) % 100000
        rng = random.Random(seed)
        samples = [
            ("TESCO STORES 4521", "Tesco", "Groceries", 18.0),
            ("PAYPAL *NEW MERCHANT", "paypal new", "Shopping", 47.0),
            ("SQ *NEW CAFE", "Unknown Cafe", "Eating Out", 9.5),
            ("AMZNMKTPLACE", "Amazon", "Shopping", 31.0),
        ]
        before_surfaced = len(service.get_pending_questions())
        before_queued = service.get_queued_question_count()
        history_locations = [
            transaction.location
            for transaction in service.get_transactions()
            if transaction.location
        ]
        now = datetime.now()
        transactions = []
        with st.spinner("Generating and categorising transactions..."):
            for offset in range(4):
                raw, clean, _, typical = rng.choice(samples)
                transactions.append(Transaction(
                    None,
                    now - timedelta(minutes=offset),
                    round(max(1.0, rng.normalvariate(typical, typical * 0.25)), 2),
                    raw,
                    clean,
                    rng.choice(history_locations) if history_locations else None,
                    category="Other",
                    confidence_score=0.0,
                    status="TENTATIVE",
                    source="SYNTHETIC",
                ))
            ingested = service.ingest_all(transactions)
        after_surfaced = len(service.get_pending_questions())
        after_queued = service.get_queued_question_count()
        st.success(
            f"Added {len(ingested)} fresh transactions; "
            f"{max(0, after_surfaced - before_surfaced)} surfaced and "
            f"{max(0, after_queued - before_queued)} queued questions."
        )

    if st.button("Reset demo data"):
        service.reset_demo_data()
        st.cache_resource.clear()
        st.rerun()

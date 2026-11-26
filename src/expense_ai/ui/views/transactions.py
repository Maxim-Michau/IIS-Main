"""Transactions Streamlit view."""

import pandas as pd
import streamlit as st


def render(service: object) -> None:
    """Show searchable transaction records."""
    st.header("Transactions")
    transactions = service.get_transactions()
    if not transactions:
        st.info("No transactions yet.")
        return
    frame = pd.DataFrame([vars(transaction) for transaction in transactions])
    search = st.text_input("Search merchant")
    if search:
        frame = frame[frame["merchant_raw"].str.contains(search, case=False, na=False)]
    st.dataframe(frame, use_container_width=True)
    st.subheader("Activity log")
    activity = service.get_activity_log(limit=30)
    if activity:
        activity_frame = pd.DataFrame(activity)
        st.dataframe(
            activity_frame[
                ["created_at", "event_type", "transaction_id", "message", "method", "confidence"]
            ],
            use_container_width=True,
        )
    else:
        st.info("No AI decisions or answers have been recorded yet.")

    st.subheader("Correct categorisation")
    selected = st.selectbox("Transaction", [f"{item.id}: {item.merchant_clean} (£{item.amount:.2f})"
                                             for item in transactions],
                            format_func=lambda value: value)
    if selected:
        transaction_id = int(selected.split(":", 1)[0])
        transaction = next(item for item in transactions if item.id == transaction_id)
        category = st.text_input("Correct category", transaction.category,
                                 key=f"category-{transaction_id}")
        col1, col2 = st.columns(2)
        if col1.button("Correct", key=f"correct-{transaction_id}"):
            try:
                message = service.correct_category(transaction_id, category)
            except ValueError as error:
                st.error(str(error))
            else:
                st.success(message)
                st.rerun()
        if col2.button("Undo", key=f"undo-{transaction_id}"):
            if service.undo_category_change(transaction_id):
                st.info("Correction undone.")
                st.rerun()
            else:
                st.info("No correction is available to undo for this transaction.")
        with st.expander("Why this category?"):
            st.write(f"Method: {transaction.method or 'RULE'}")
            st.write(f"Confidence: {transaction.confidence_score:.0%}")
            st.write(transaction.explanation or "No explanation was recorded.")
    with st.expander(f"History for transaction {transaction_id}"):
        history = service.get_activity_log(transaction_id=transaction_id)
        if history:
            st.dataframe(pd.DataFrame(history), use_container_width=True)
        else:
            st.info("No history is recorded for this transaction.")

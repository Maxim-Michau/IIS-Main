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
            previous = transaction.category
            transaction.category = category
            transaction.status = "CORRECTED"
            service.repository.update(transaction)
            st.success(f"Changed {transaction.merchant_clean} to {category}")
        if col2.button("Undo", key=f"undo-{transaction_id}"):
            transaction.status = "TENTATIVE"
            service.repository.update(transaction)
            st.info("Correction undone")
        with st.expander("Why this category?"):
            st.write(f"Method: {transaction.method or 'RULE'}")
            st.write(f"Confidence: {transaction.confidence_score:.0%}")
            st.write(transaction.explanation or "No explanation was recorded.")

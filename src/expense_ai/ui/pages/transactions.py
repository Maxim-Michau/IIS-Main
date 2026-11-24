"""Transactions Streamlit page."""

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

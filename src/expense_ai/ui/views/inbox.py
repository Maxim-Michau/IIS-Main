"""Merchant-grouped simulated notification inbox."""

from collections import Counter, defaultdict

import streamlit as st

from expense_ai.ai.categorisers.recurrence import RecurrenceDetector


CATEGORIES = [
    "Groceries", "Eating Out", "Takeaways", "Transport", "Rent & Bills",
    "Subscriptions", "Shopping", "Entertainment", "Education",
    "Health & Fitness", "Travel", "Other",
]


def render(service: object) -> None:
    """Render one answer card per merchant."""
    st.header("Inbox")
    st.caption("Simulated push notifications")
    message = st.session_state.pop("last_feedback_message", None)
    if message:
        st.success(message)
        st.toast(message)
    if service.get_last_category_action() and st.button("Undo last category answer"):
        if service.undo_category_change():
            st.info("Last category answer undone.")
            st.rerun()

    questions = service.get_pending_questions()
    queued_count = service.get_queued_question_count()
    if queued_count:
        st.info(f"{queued_count} more questions queued.")
        if st.button("Release next batch (ignores daily cap)"):
            service.release_next_question_batch()
            st.rerun()
    if not questions:
        st.success("No pending questions.")
        return
    transactions = service.get_transactions()
    by_id = {transaction.id: transaction for transaction in transactions}
    usual_locations = Counter(
        transaction.location for transaction in transactions if transaction.location
    )
    by_merchant: dict[str, list[dict[str, object]]] = defaultdict(list)
    for question in questions:
        transaction = by_id.get(question["transaction_id"])
        if transaction:
            by_merchant[transaction.merchant_clean].append(question)

    for merchant, merchant_questions in by_merchant.items():
        pending_ids = {question["transaction_id"] for question in merchant_questions}
        merchant_transactions = [
            item for item in transactions if item.merchant_clean == merchant
        ]
        pending_transactions = [
            by_id[transaction_id] for transaction_id in pending_ids if transaction_id in by_id
        ]
        representative = pending_transactions[0]
        with st.container(border=True):
            st.subheader(representative.merchant_raw)
            st.caption(f"Cleaned merchant: {merchant}")
            st.markdown("**Pending transactions**")
            for transaction in sorted(pending_transactions, key=lambda item: item.timestamp):
                st.write(
                    f"{transaction.timestamp:%Y-%m-%d %H:%M} · "
                    f"GBP {transaction.amount:.2f} · {transaction.location or 'Location unknown'} · "
                    f"{transaction.category} · {transaction.method} · "
                    f"{transaction.confidence_score:.0%}"
                )
                st.caption(transaction.explanation or "No explanation recorded.")

            previous = sorted(
                (item for item in merchant_transactions if item.id not in pending_ids),
                key=lambda item: item.timestamp,
                reverse=True,
            )
            locations = Counter(item.location for item in previous if item.location)
            weekdays = Counter(item.timestamp.strftime("%A") for item in previous)
            if previous:
                st.markdown("**Your previous transactions at this merchant**")
                for item in previous[:5]:
                    st.write(f"{item.timestamp:%Y-%m-%d} · GBP {item.amount:.2f}")
                average = sum(item.amount for item in previous) / len(previous)
                usual_location = locations.most_common(1)[0][0] if locations else "Unknown"
                usual_weekday = weekdays.most_common(1)[0][0] if weekdays else "Unknown"
                st.caption(
                    f"Average GBP {average:.2f} · Usual location: {usual_location} · "
                    f"Usual weekday: {usual_weekday}"
                )

            recurrence = RecurrenceDetector(service.repository.engine).detect(
                representative, merchant_transactions
            )
            if recurrence.count >= 3:
                amounts = [item.amount for item in merchant_transactions]
                low, high = min(amounts), max(amounts)
                days = {"weekly": 7, "fortnightly": 14, "monthly": 30}.get(
                    recurrence.interval
                )
                if days:
                    pattern = f"about every {days} days"
                else:
                    pattern = "with no consistent interval"
                st.info(
                    f"Detected pattern: {recurrence.count} payments of GBP {low:.0f}-{high:.0f} "
                    f"{pattern}."
                )
            else:
                st.caption("Detected pattern: not enough repeated payments yet.")

            questions_by_type: dict[str, list[dict[str, object]]] = defaultdict(list)
            for question in merchant_questions:
                questions_by_type[question["question_type"]].append(question)
            for question_type, grouped_questions in questions_by_type.items():
                question = grouped_questions[0]
                question_id = question["id"]
                st.markdown(f"**{question['prompt_text']}**")
                if question_type == "CATEGORY":
                    _category_controls(service, question_id, grouped_questions)
                elif question_type == "LOCATION":
                    _location_controls(service, question_id, usual_locations)
                else:
                    options = list(dict.fromkeys(
                        option for item in grouped_questions
                        for option in str(item["options"] or "").split("|") if option
                    ))
                    for index, option in enumerate(options):
                        if st.button(
                            option, key=f"q-{question_id}-option-{index}"
                        ):
                            _answer(service, question_id, option)
                            st.rerun()
                    if question_type == "EXTRA_INFO":
                        note = st.text_input(
                            "Add a note",
                            key=f"q-{question_id}-note-{len(options)}",
                        )
                        if st.button(
                            "Save note", key=f"q-{question_id}-save-note-{len(options) + 1}"
                        ) and note.strip():
                            _answer(service, question_id, note.strip())
                            st.rerun()


def _category_controls(
    service: object,
    question_id: int,
    questions: list[dict[str, object]],
) -> None:
    suggestions = list(dict.fromkeys(
        option for question in questions
        for option in str(question["options"] or "").split("|")
        if option
    ))[:3]
    for index, category in enumerate(suggestions):
        if st.button(category, key=f"q-{question_id}-category-button-{index}"):
            _answer(service, question_id, category)
            st.rerun()

    categories = list(dict.fromkeys(CATEGORIES + suggestions))
    selected = st.selectbox(
        "All categories",
        categories,
        key=f"q-{question_id}-category-select-{len(suggestions)}",
    )
    custom = st.text_input(
        "New custom category",
        key=f"q-{question_id}-custom-category-{len(suggestions) + 1}",
    )
    if st.button(
        "Apply category",
        key=f"q-{question_id}-category-apply-{len(suggestions) + 2}",
    ):
        _answer(service, question_id, custom.strip() or selected)
        st.rerun()


def _location_controls(
    service: object,
    question_id: int,
    locations: Counter[str],
) -> None:
    usual_locations = [location for location, _ in locations.most_common(3)]
    for index, location in enumerate(usual_locations):
        if st.button(location, key=f"q-{question_id}-location-button-{index}"):
            _answer(service, question_id, location)
            st.rerun()
    location = st.text_input(
        "Location",
        key=f"q-{question_id}-location-input-{len(usual_locations)}",
    )
    if st.button(
        "Save location",
        key=f"q-{question_id}-location-save-{len(usual_locations) + 1}",
    ) and location.strip():
        _answer(service, question_id, location.strip())
        st.rerun()


def _answer(service: object, question_id: int, answer: str) -> None:
    message = service.answer_question(question_id, answer)
    if message:
        st.session_state.last_feedback_message = message

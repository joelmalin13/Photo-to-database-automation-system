"""Document verification and field correction interface for SnapBase.

Displays original image side-by-side with an editable form, highlights
low-confidence extractions, and supports Approve, Save Edits, and Reject workflows.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import streamlit as st

from config.settings import CONFIDENCE_THRESHOLD, DocumentStatus, load_schemas
from db.crud import (
    get_document_by_id,
    list_documents,
    update_document_fields,
    update_document_status,
)
from db.models import Document
from db.session import get_db_session, init_db
from ui.components import (
    get_status_badge_html,
    render_confidence_indicator,
    render_empty_state,
    render_header,
)
from ui.styles import inject_css

# Page Configuration
st.set_page_config(
    page_title="Review & Verify | SnapBase",
    page_icon="📝",
    layout="wide",
)
inject_css()
init_db()

render_header(
    title="Document Review & Verification",
    subtitle="Inspect extracted fields side-by-side with document photography and correct low-confidence values",
)

schemas = load_schemas()

# Query pending and all documents
with get_db_session() as session:
    all_docs, _ = list_documents(
        session, page=1, page_size=100, sort_by="created_at", sort_order="desc"
    )

if not all_docs:
    render_empty_state(
        message="No documents available to review.",
        hint="Upload documents via the Upload page or drop images in the /inbox directory.",
    )
    if st.button("Go to Upload Page", type="primary"):
        st.switch_page("pages/1_Upload.py")
    st.stop()

# Document Selector
filter_pending = st.checkbox("Show only pending documents", value=False)
selectable_docs = [
    d
    for d in all_docs
    if not filter_pending or d.status == DocumentStatus.PENDING.value
]

if not selectable_docs:
    st.info("No documents match the pending filter.")
    st.stop()

# Resolve currently active document ID
doc_options = {
    f"#{d.id} | {d.filename} ({d.type}) — [{d.status.upper()}]": d.id
    for d in selectable_docs
}
default_id = st.session_state.get("review_doc_id", selectable_docs[0].id)
selected_label = next(
    (k for k, v in doc_options.items() if v == default_id),
    list(doc_options.keys())[0],
)

chosen_label = st.selectbox(
    "Select Document to Inspect",
    options=list(doc_options.keys()),
    index=list(doc_options.keys()).index(selected_label),
)
selected_doc_id = doc_options[chosen_label]

with get_db_session() as session:
    current_doc: Document | None = get_document_by_id(session, selected_doc_id)
    if not current_doc:
        st.error("Selected document could not be found.")
        st.stop()

    doc_data = current_doc.to_dict()

# Side-by-side verification layout
col_img, col_form = st.columns([1, 1], gap="large")

with col_img:
    st.markdown("### 📷 Document Photo")
    img_path = Path(doc_data["image_path"])
    if img_path.exists():
        st.image(str(img_path), use_container_width=True)
    else:
        st.warning(f"Image file missing on disk: {img_path}")

    st.markdown(
        f"""
        <div class="snapbase-card" style="margin-top: 10px; font-size: 0.88rem;">
            <b>Filename:</b> {doc_data['filename']}<br>
            <b>SHA-256 Hash:</b> <code>{doc_data['image_hash'][:16]}...</code><br>
            <b>Ingested:</b> {doc_data['created_at']}<br>
            <b>Status:</b> {get_status_badge_html(doc_data['status'])}
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_form:
    st.markdown("### ✍️ Extracted Fields & Validation")
    doc_fields: Dict[str, Any] = doc_data.get("fields", {})
    doc_confidences: Dict[str, float] = doc_data.get("field_confidences", {})
    doc_type = doc_data["type"]
    schema_def = schemas.get(doc_type, {})
    schema_fields = {f["key"]: f for f in schema_def.get("fields", [])}

    # Identify low confidence fields
    low_conf_keys = [
        k for k, conf in doc_confidences.items() if conf < CONFIDENCE_THRESHOLD
    ]
    if low_conf_keys:
        st.markdown(
            f"""
            <div class="low-confidence-box">
                ⚠️ <b>Low-Confidence Notice:</b> The following fields have confidence below {int(CONFIDENCE_THRESHOLD * 100)}%:
                <b>{", ".join(low_conf_keys)}</b>. Please review and verify.
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Editable form
    with st.form(key=f"edit_form_{selected_doc_id}"):
        input_values: Dict[str, Any] = {}
        all_field_keys = list(schema_fields.keys()) or list(doc_fields.keys())

        for k in all_field_keys:
            label = schema_fields.get(k, {}).get("label", k.replace("_", " ").title())
            current_val = doc_fields.get(k, "")
            confidence = doc_confidences.get(k, 1.0)
            badge_html = render_confidence_indicator(confidence)

            st.markdown(
                f"<div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;'>"
                f"<label style='font-weight: 600; font-size: 0.88rem;'>{label}</label>"
                f"{badge_html}"
                f"</div>",
                unsafe_allow_html=True,
            )
            input_values[k] = st.text_input(
                label=label,
                value=str(current_val) if current_val is not None else "",
                key=f"field_{selected_doc_id}_{k}",
                label_visibility="collapsed",
            )

        st.markdown("<br>", unsafe_allow_html=True)
        col_act1, col_act2, col_act3 = st.columns(3)

        with col_act1:
            submitted_approve = st.form_submit_button(
                "✅ Approve / Save",
                type="primary",
                use_container_width=True,
            )
        with col_act2:
            submitted_save = st.form_submit_button(
                "💾 Save Edits Only",
                use_container_width=True,
            )
        with col_act3:
            submitted_reject = st.form_submit_button(
                "❌ Reject Document",
                use_container_width=True,
            )

    # Process Form Submissions
    if submitted_approve or submitted_save or submitted_reject:
        with get_db_session() as session:
            if submitted_reject:
                update_document_status(
                    session, selected_doc_id, DocumentStatus.REJECTED.value
                )
                st.toast("Document marked as Rejected.", icon="❌")
            else:
                update_document_fields(session, selected_doc_id, input_values)
                if submitted_approve:
                    update_document_status(
                        session, selected_doc_id, DocumentStatus.PROCESSED.value
                    )
                    st.toast("Document approved and saved!", icon="✅")
                else:
                    st.toast("Document edits persisted.", icon="💾")
        st.rerun()

    # Line items display
    if doc_data.get("line_items"):
        st.markdown("#### 📋 Tabular Line Items")
        st.dataframe(doc_data["line_items"], use_container_width=True)

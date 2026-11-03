"""SnapBase: Photo to Database Automation Platform.

Streamlit Cloud entry point providing interactive document ingestion,
split-view verification, repository management, and operational analytics.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st

from config.settings import (
    ALLOWED_EXTENSIONS,
    CONFIDENCE_THRESHOLD,
    DEFAULT_ENGINE,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    THEME_PRIMARY,
    DocumentStatus,
    load_schemas,
    logger,
)
from core.pipeline import batch_process_images, process_single_image
from db.crud import (
    create_document,
    delete_document,
    get_dashboard_metrics,
    get_document_by_id,
    list_documents,
    update_document_fields,
    update_document_status,
)
from db.models import Base
from db.session import get_db_session, init_db

# Initialize database schema idempotently
init_db()

# Page Configuration
st.set_page_config(
    page_title="SnapBase | Photo to Database",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling (Professional SaaS palette)
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    .main-header {
        background: #111111;
        border-bottom: 3px solid #C62828;
        padding: 18px 24px;
        border-radius: 8px;
        margin-bottom: 24px;
        color: #FFFFFF;
    }
    .metric-card {
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 10px;
        padding: 16px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .badge-approved {
        background-color: #ECFDF5;
        color: #047857;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 600;
        border: 1px solid #A7F3D0;
    }
    .badge-pending {
        background-color: #FFFBEB;
        color: #B45309;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 600;
        border: 1px solid #FDE68A;
    }
    .badge-rejected {
        background-color: #FFF1F2;
        color: #BE123C;
        padding: 2px 8px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 600;
        border: 1px solid #FECDD3;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def render_header(title: str, subtitle: str) -> None:
    """Render top header bar."""
    st.markdown(
        f"""
        <div class="main-header">
            <div style="font-size: 22px; font-weight: 800; letter-spacing: -0.5px;">SnapBase: {title}</div>
            <div style="font-size: 12px; color: #9CA3AF; margin-top: 4px;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_navigation() -> str:
    """Render unified navigation and engine status sidebar."""
    with st.sidebar:
        st.markdown(
            """
            <div style="font-size: 20px; font-weight: 900; color: #111827; margin-bottom: 2px;">
                SnapBase
            </div>
            <div style="font-size: 11px; color: #6B7280; margin-bottom: 20px;">
                Photo to Database System
            </div>
            """,
            unsafe_allow_html=True,
        )

        nav = st.radio(
            "Navigation",
            ["Dashboard", "Upload Documents", "Review & Verify", "Records Repository", "Settings"],
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.caption("Engine Status")
        if GEMINI_API_KEY:
            st.success("Gemini API: Connected")
        else:
            st.info("Engine: Local Offline OCR")

        st.caption(f"Model: {GEMINI_MODEL}")
        st.caption(f"Review Gate: {int(CONFIDENCE_THRESHOLD * 100)}%")

        st.markdown("---")
        st.caption("GitHub: joelmalin13/Photo-to-database-automation-system")

    return nav


# ---------------------------------------------------------------------------
# View 1: Dashboard
# ---------------------------------------------------------------------------
def view_dashboard() -> None:
    render_header("Operational Dashboard", "Real-time document ingestion KPIs and validation metrics")

    with get_db_session() as session:
        metrics = get_dashboard_metrics(session)
        recent_docs, total = list_documents(session, page=1, page_size=6, sort_by="created_at", sort_order="desc")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Ingested", metrics["total_documents"])
    with col2:
        st.metric("Approved Records", metrics["status_counts"].get("processed", 0))
    with col3:
        st.metric("Pending Verification", metrics["status_counts"].get("pending", 0))
    with col4:
        acc = f"{metrics['accuracy_rate']:.1f}%" if metrics["total_documents"] > 0 else "No data"
        st.metric("Extraction Accuracy", acc)

    st.markdown("### Recent Activity Feed")
    if recent_docs:
        feed_data = []
        for d in recent_docs:
            feed_data.append(
                {
                    "ID": d.id,
                    "Filename": d.filename,
                    "Type": d.type.replace("_", " ").title(),
                    "Status": d.status.title(),
                    "Date Ingested": d.created_at.strftime("%Y-%m-%d %H:%M") if d.created_at else "N/A",
                }
            )
        st.dataframe(pd.DataFrame(feed_data), use_container_width=True, hide_index=True)
    else:
        st.info("No documents have been ingested yet. Navigate to 'Upload Documents' to process your first receipt or form.")


# ---------------------------------------------------------------------------
# View 2: Upload Documents
# ---------------------------------------------------------------------------
def view_upload() -> None:
    render_header("Upload & Ingestion", "Upload document photographs or capture via webcam for automated extraction")

    schemas = load_schemas()
    schema_options = ["Auto-detect"] + [s.replace("_", " ").title() for s in schemas.keys()]
    schema_keys = ["auto"] + list(schemas.keys())

    col_cfg1, col_cfg2 = st.columns([2, 1])
    with col_cfg1:
        selected_display = st.selectbox("Document Classification Target", schema_options)
        selected_doc_type = schema_keys[schema_options.index(selected_display)]
    with col_cfg2:
        preferred_engine = st.selectbox("Preferred Engine", ["gemini", "ocr"])

    tab_file, tab_cam = st.tabs(["File Upload", "Camera Snapshot"])

    uploaded_files = []
    with tab_file:
        files = st.file_uploader(
            "Select or drop document photos (.jpg, .jpeg, .png, .webp)",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
        )
        if files:
            uploaded_files = [(f.read(), f.name) for f in files]

    with tab_cam:
        cam_photo = st.camera_input("Take a document photo")
        if cam_photo:
            uploaded_files = [(cam_photo.read(), "webcam_capture.jpg")]

    if uploaded_files:
        st.write(f"Ready to process **{len(uploaded_files)}** item(s)")
        if st.button("Start Extraction Pipeline", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()

            results = []
            for idx, (img_bytes, fname) in enumerate(uploaded_files):
                status_text.text(f"Processing {fname} ({idx + 1}/{len(uploaded_files)})...")
                try:
                    res = process_single_image(
                        image_bytes=img_bytes,
                        filename=fname,
                        doc_type=selected_doc_type,
                        preferred_engine=preferred_engine,
                        auto_save=True,
                    )
                    results.append(res)
                except Exception as exc:
                    st.error(f"Error processing {fname}: {exc}")
                progress_bar.progress((idx + 1) / len(uploaded_files))

            status_text.text("Ingestion completed successfully!")

            for res in results:
                if res.is_duplicate:
                    st.warning(f"Duplicate image detected: '{res.filename}' matches existing Document #{res.document_id}")
                else:
                    st.success(f"Document #{res.document_id} ('{res.filename}') extracted successfully. Status: {res.status}")
                    with st.expander(f"Extracted Fields - {res.filename}"):
                        st.json(res.fields)


# ---------------------------------------------------------------------------
# View 3: Review & Verify
# ---------------------------------------------------------------------------
def view_review() -> None:
    render_header("Review & Verify", "Inspect original document images and edit extracted attributes")

    with get_db_session() as session:
        pending_docs, _ = list_documents(session, status=DocumentStatus.PENDING.value, page=1, page_size=50)
        all_docs, _ = list_documents(session, page=1, page_size=100)

    target_docs = pending_docs if pending_docs else all_docs
    if not target_docs:
        st.info("No documents found in the database. Please upload document images first.")
        return

    doc_options = {f"Doc #{d.id} - {d.filename} ({d.status})": d.id for d in target_docs}
    selected_label = st.selectbox("Select Document for Inspection", list(doc_options.keys()))
    doc_id = doc_options[selected_label]

    with get_db_session() as session:
        doc = get_document_by_id(session, doc_id)
        if not doc:
            st.error("Document not found.")
            return

        doc_dict = doc.to_dict()

    col_img, col_form = st.columns([1, 1], gap="large")

    with col_img:
        st.subheader("Source Photograph")
        img_path = Path(doc_dict["image_path"])
        if img_path.exists():
            st.image(str(img_path), use_container_width=True)
        else:
            st.warning("Original image file not found on disk.")

        st.caption(f"Filename: {doc_dict['filename']} | Hash: {doc_dict['image_hash'][:12]}...")

    with col_form:
        st.subheader("Extracted Attributes")
        st.caption(f"Status: {doc_dict['status'].upper()} | Average Confidence: {doc_dict['confidence'] * 100:.0f}%")

        edited_fields = {}
        for k, v in doc_dict["fields"].items():
            conf = doc_dict["field_confidences"].get(k, 1.0)
            conf_pct = int(conf * 100)
            label = f"{k.replace('_', ' ').title()} ({conf_pct}% confidence)"
            if conf < CONFIDENCE_THRESHOLD:
                label += " [LOW CONFIDENCE]"
            edited_fields[k] = st.text_input(label, value=str(v if v is not None else ""))

        col_act1, col_act2, col_act3 = st.columns(3)
        with col_act1:
            if st.button("Approve Record", type="primary"):
                with get_db_session() as session:
                    update_document_fields(session, doc_id, edited_fields)
                    update_document_status(session, doc_id, DocumentStatus.PROCESSED.value)
                st.success(f"Document #{doc_id} marked as Approved.")
                st.rerun()

        with col_act2:
            if st.button("Save Edits"):
                with get_db_session() as session:
                    update_document_fields(session, doc_id, edited_fields)
                st.info("Field edits persisted.")
                st.rerun()

        with col_act3:
            if st.button("Reject Record"):
                with get_db_session() as session:
                    update_document_status(session, doc_id, DocumentStatus.REJECTED.value)
                st.warning(f"Document #{doc_id} marked as Rejected.")
                st.rerun()


# ---------------------------------------------------------------------------
# View 4: Records Repository
# ---------------------------------------------------------------------------
def view_records() -> None:
    render_header("Records Repository", "Search, filter, inspect, and export verified datasets")

    col_flt1, col_flt2, col_search = st.columns([1, 1, 2])
    with col_flt1:
        status_flt = st.selectbox("Status Filter", ["All", "pending", "processed", "rejected"])
    with col_flt2:
        schemas = load_schemas()
        type_options = ["All"] + list(schemas.keys())
        type_flt = st.selectbox("Document Type", type_options)
    with col_search:
        search_query = st.text_input("Live Search", placeholder="Search by vendor, ID number, or filename...")

    with get_db_session() as session:
        docs, total = list_documents(
            session,
            doc_type=type_flt if type_flt != "All" else None,
            status=status_flt if status_flt != "All" else None,
            search_query=search_query or None,
            page=1,
            page_size=200,
        )

    st.write(f"Showing **{len(docs)}** of **{total}** records")

    if docs:
        records_data = []
        for d in docs:
            d_dict = d.to_dict()
            row = {
                "ID": d_dict["id"],
                "Filename": d_dict["filename"],
                "Type": d_dict["type"],
                "Status": d_dict["status"],
                "Confidence": f"{d_dict['confidence'] * 100:.0f}%",
                "Created At": d_dict["created_at"][:16] if d_dict["created_at"] else "",
            }
            # Flatten extracted fields
            for fk, fv in d_dict["fields"].items():
                row[fk] = fv
            records_data.append(row)

        df = pd.DataFrame(records_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        col_exp1, col_exp2, col_exp3 = st.columns(3)
        with col_exp1:
            csv_buf = df.to_csv(index=False).encode("utf-8")
            st.download_button("Export as CSV", data=csv_buf, file_name="snapbase_records.csv", mime="text/csv")
        with col_exp2:
            json_buf = df.to_json(orient="records", indent=2).encode("utf-8")
            st.download_button("Export as JSON", data=json_buf, file_name="snapbase_records.json", mime="application/json")
        with col_exp3:
            excel_buf = io.BytesIO()
            df.to_excel(excel_buf, index=False, engine="openpyxl")
            st.download_button(
                "Export as Excel",
                data=excel_buf.getvalue(),
                file_name="snapbase_records.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    else:
        st.info("No matching records found for the applied filter.")


# ---------------------------------------------------------------------------
# View 5: Settings
# ---------------------------------------------------------------------------
def view_settings() -> None:
    render_header("System Settings", "Configure extraction engines and validation thresholds")

    st.subheader("Extraction Engine")
    st.write(f"Default Active Engine: **{DEFAULT_ENGINE.upper()}**")
    st.write(f"Active Gemini Model: `{GEMINI_MODEL}`")
    st.write(f"Gemini API Key Configured: **{'Yes' if GEMINI_API_KEY else 'No (Running Local Offline OCR)'}**")

    st.markdown("---")
    st.subheader("Review Confidence Gates")
    threshold = st.slider("Minimum Confidence Threshold", 40, 95, int(CONFIDENCE_THRESHOLD * 100), step=5)
    st.caption(f"Documents below {threshold}% confidence will automatically require manual verification.")


# ---------------------------------------------------------------------------
# Application Dispatcher
# ---------------------------------------------------------------------------
def main() -> None:
    view = sidebar_navigation()
    if view == "Dashboard":
        view_dashboard()
    elif view == "Upload Documents":
        view_upload()
    elif view == "Review & Verify":
        view_review()
    elif view == "Records Repository":
        view_records()
    elif view == "Settings":
        view_settings()


if __name__ == "__main__":
    main()

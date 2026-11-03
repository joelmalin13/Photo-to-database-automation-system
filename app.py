"""SnapBase main entrypoint and welcome portal.

Provides system overview, engine readiness status, quick navigation cards,
and initializes database tables idempotently.
"""

from __future__ import annotations

import streamlit as st

from config.settings import (
    DEFAULT_ENGINE,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    THEME_PRIMARY,
)
from db.crud import get_dashboard_metrics
from db.session import get_db_session, init_db
from ui.components import render_header, render_metric_card
from ui.styles import inject_css

# Configure page parameters
st.set_page_config(
    page_title="SnapBase | Photo to Database",
    page_icon="📷",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply global branding and initialize database
inject_css()
init_db()

# Render Brand Header
render_header(
    title="SnapBase: Photo to Database",
    subtitle="Automated document processing, intelligent field extraction, and relational persistence",
)

# Sidebar System Information
with st.sidebar:
    st.markdown("### ⚙️ System Status")
    gemini_status = "🟢 Active" if GEMINI_API_KEY else "⚪ Not Configured (.env)"
    st.markdown(f"**Gemini Vision:** {gemini_status}")
    if GEMINI_API_KEY:
        st.caption(f"Model: `{GEMINI_MODEL}`")
    st.markdown("**Offline OCR:** 🟢 Ready (EasyOCR + Regex)")
    st.markdown(f"**Default Engine:** `{DEFAULT_ENGINE.upper()}`")
    st.divider()
    st.markdown("### 📚 Navigation")
    st.page_link("pages/1_Upload.py", label="1. Ingest Documents", icon="📤")
    st.page_link("pages/2_Review.py", label="2. Review & Verify", icon="📝")
    st.page_link("pages/3_Records.py", label="3. Records & Export", icon="📂")
    st.page_link("pages/4_Dashboard.py", label="4. System Analytics", icon="📊")

# Top High-Level Metrics
with get_db_session() as session:
    metrics = get_dashboard_metrics(session)

m_col1, m_col2, m_col3, m_col4 = st.columns(4)
with m_col1:
    render_metric_card("Total Documents", metrics["total_documents"], "Ingested photos")
with m_col2:
    render_metric_card(
        "Pending Review", metrics["status_counts"]["pending"], "Awaiting verification"
    )
with m_col3:
    render_metric_card(
        "Approved Records", metrics["status_counts"]["processed"], "Verified & stored"
    )
with m_col4:
    render_metric_card(
        "Field Accuracy", f"{metrics['accuracy_rate']}%", "Unedited rate"
    )

st.markdown("<br>", unsafe_allow_html=True)

# Functional Navigation Cards
col_card1, col_card2, col_card3 = st.columns(3)

with col_card1:
    st.markdown(
        """
        <div class="snapbase-card">
            <h3 style="color: #C62828; margin-top: 0;">📤 1. Ingest Photos</h3>
            <p style="color: #616161;">Upload receipts, invoices, student IDs, or tables. Choose files or snap directly with your webcam.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Go to Upload Page", key="btn_nav_upload", use_container_width=True):
        st.switch_page("pages/1_Upload.py")

with col_card2:
    st.markdown(
        """
        <div class="snapbase-card">
            <h3 style="color: #C62828; margin-top: 0;">📝 2. Review & Correct</h3>
            <p style="color: #616161;">Compare original photos side-by-side with editable fields. Low-confidence extractions are highlighted.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Go to Review Page", key="btn_nav_review", use_container_width=True):
        st.switch_page("pages/2_Review.py")

with col_card3:
    st.markdown(
        """
        <div class="snapbase-card">
            <h3 style="color: #C62828; margin-top: 0;">📂 3. Search & Export</h3>
            <p style="color: #616161;">Filter records by status, type, and date. Search full-text fields and export instantly to CSV, Excel, or JSON.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Go to Records Page", key="btn_nav_records", use_container_width=True):
        st.switch_page("pages/3_Records.py")

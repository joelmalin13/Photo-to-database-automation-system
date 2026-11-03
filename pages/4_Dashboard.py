"""Operational analytics and visualization dashboard for SnapBase.

Renders metrics for ingestion volume, processing statuses, automated
extraction accuracy vs manual edits, and Plotly charts using brand palette.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config.settings import THEME_PRIMARY, THEME_SECONDARY
from db.crud import get_dashboard_metrics, list_documents
from db.session import get_db_session, init_db
from ui.components import render_empty_state, render_header, render_metric_card
from ui.styles import inject_css

# Page Configuration
st.set_page_config(
    page_title="Analytics Dashboard | SnapBase",
    page_icon="📊",
    layout="wide",
)
inject_css()
init_db()

render_header(
    title="System Analytics & Metrics",
    subtitle="Operational overview of document ingestion throughput, field extraction accuracy, and status breakdowns",
)

with get_db_session() as session:
    metrics = get_dashboard_metrics(session)
    docs, _ = list_documents(session, page=1, page_size=1000)

if metrics["total_documents"] == 0:
    render_empty_state(
        message="No document data available for analytics.",
        hint="Upload documents via the Upload page or /inbox to populate dashboard metrics.",
    )
    st.stop()

# Top Metric Summary Cards
m_c1, m_c2, m_c3, m_c4 = st.columns(4)
with m_c1:
    render_metric_card("Total Documents", metrics["total_documents"], "Ingested photos")
with m_c2:
    render_metric_card(
        "Approved Records", metrics["status_counts"]["processed"], "Verified & stored"
    )
with m_c3:
    render_metric_card(
        "Pending Verification", metrics["status_counts"]["pending"], "Awaiting user review"
    )
with m_c4:
    render_metric_card(
        "Extraction Accuracy", f"{metrics['accuracy_rate']}%", "Unedited rate"
    )

st.markdown("<br>", unsafe_allow_html=True)

# Visual Charts Section
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.markdown("#### 🍩 Document Processing Status")
    status_data = pd.DataFrame(
        {
            "Status": ["Approved", "Pending", "Rejected"],
            "Count": [
                metrics["status_counts"]["processed"],
                metrics["status_counts"]["pending"],
                metrics["status_counts"]["rejected"],
            ],
        }
    )
    status_data = status_data[status_data["Count"] > 0]

    color_map = {
        "Approved": "#2E7D32",
        "Pending": "#F57C00",
        "Rejected": "#C62828",
    }
    fig_status = px.pie(
        status_data,
        names="Status",
        values="Count",
        hole=0.45,
        color="Status",
        color_discrete_map=color_map,
    )
    fig_status.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(t=10, b=10, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=-0.2),
        font=dict(color="#1F1F1F"),
    )
    st.plotly_chart(fig_status, use_container_width=True)

with col_chart2:
    st.markdown("#### 📊 Documents by Classification Type")
    type_counts = metrics.get("type_counts", {})
    type_df = pd.DataFrame(
        {
            "Document Type": [k.replace("_", " ").title() for k in type_counts.keys()],
            "Count": list(type_counts.values()),
        }
    )
    fig_type = px.bar(
        type_df,
        x="Document Type",
        y="Count",
        color_discrete_sequence=[THEME_PRIMARY],
        text="Count",
    )
    fig_type.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(t=10, b=10, l=10, r=10),
        font=dict(color="#1F1F1F"),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor="#E5E5E5"),
    )
    fig_type.update_traces(textposition="outside")
    st.plotly_chart(fig_type, use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)

col_chart3, col_chart4 = st.columns(2)

with col_chart3:
    st.markdown("#### 🎯 Automation Efficiency: Edited vs Unedited")
    acc_df = pd.DataFrame(
        {
            "Category": ["Zero-Edit (Perfect)", "User Corrected"],
            "Documents": [metrics["unedited_count"], metrics["edited_count"]],
        }
    )
    fig_acc = px.bar(
        acc_df,
        x="Category",
        y="Documents",
        color="Category",
        color_discrete_map={
            "Zero-Edit (Perfect)": "#111111",
            "User Corrected": "#C62828",
        },
        text="Documents",
    )
    fig_acc.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(t=10, b=10, l=10, r=10),
        font=dict(color="#1F1F1F"),
        showlegend=False,
        yaxis=dict(showgrid=True, gridcolor="#E5E5E5"),
    )
    fig_acc.update_traces(textposition="outside")
    st.plotly_chart(fig_acc, use_container_width=True)

with col_chart4:
    st.markdown("#### ⚡ System Performance Summary")
    st.markdown(
        f"""
        <div class="snapbase-card">
            <p><b>Average Field Confidence:</b> {metrics.get('average_confidence', 0)}%</p>
            <p><b>Total Processed:</b> {metrics['total_documents']} documents</p>
            <p><b>Automated Verification Rate:</b> {metrics['accuracy_rate']}%</p>
            <p><b>Database Location:</b> <code>snapbase.db</code></p>
            <p><b>Storage Strategy:</b> Local preprocessed image store + SQLite relational tables</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

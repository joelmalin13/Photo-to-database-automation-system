"""CSS injection and visual design tokens for SnapBase.

Provides consistent white theme, black-to-red gradient banners, red accent
buttons, colored status badges, card shadows, and low-confidence highlights.
"""

from __future__ import annotations

import streamlit as st


def inject_css() -> None:
    """Inject centralized custom CSS to maintain strict brand presentation."""
    custom_css = """
    <style>
    /* Global Background and Typography */
    .stApp {
        background-color: #FFFFFF !important;
        color: #1F1F1F !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    /* Top Brand Header Banner */
    .snapbase-banner {
        background: linear-gradient(135deg, #111111 0%, #2A0808 45%, #C62828 100%);
        color: #FFFFFF !important;
        padding: 24px 32px;
        border-radius: 0 0 16px 16px;
        margin: -4rem -4rem 2rem -4rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
    }
    .snapbase-banner h1 {
        color: #FFFFFF !important;
        font-weight: 800;
        font-size: 2.1rem;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .snapbase-banner p {
        color: #FFCDD2 !important;
        font-size: 1rem;
        margin: 6px 0 0 0;
        opacity: 0.95;
    }

    /* Primary Accent Buttons */
    .stButton > button[kind="primary"], .stButton > button {
        background-color: #C62828 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.25rem !important;
        transition: all 0.2s ease-in-out !important;
        box-shadow: 0 2px 6px rgba(198, 40, 40, 0.25) !important;
    }
    .stButton > button:hover {
        background-color: #111111 !important;
        color: #FFFFFF !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2) !important;
    }

    /* White Metric and Feature Cards */
    .snapbase-card {
        background: #FFFFFF;
        border: 1px solid #E5E5E5;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
        margin-bottom: 1rem;
        transition: transform 0.2s ease;
    }
    .snapbase-card:hover {
        border-color: #D32F2F;
    }

    /* Low Confidence Field Alert */
    .low-confidence-box {
        background-color: #FFF8E1;
        border-left: 4px solid #FFA000;
        padding: 10px 14px;
        border-radius: 4px;
        margin-bottom: 12px;
        font-size: 0.9rem;
    }

    /* Status Badges */
    .badge-processed {
        background-color: #E8F5E9;
        color: #2E7D32;
        border: 1px solid #A5D6A7;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.82rem;
        display: inline-block;
    }
    .badge-pending {
        background-color: #FFF3E0;
        color: #E65100;
        border: 1px solid #FFCC80;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.82rem;
        display: inline-block;
    }
    .badge-rejected {
        background-color: #FFEBEE;
        color: #C62828;
        border: 1px solid #EF9A9A;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.82rem;
        display: inline-block;
    }

    /* Sidebar Navigation Polish */
    [data-testid="stSidebar"] {
        background-color: #FAFAFA !important;
        border-right: 1px solid #E5E5E5 !important;
    }
    [data-testid="stSidebarNav"] a[aria-current="page"] {
        border-left: 4px solid #C62828 !important;
        background-color: #FFFFFF !important;
        font-weight: 700 !important;
    }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

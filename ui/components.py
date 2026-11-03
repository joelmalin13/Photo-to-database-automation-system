"""Reusable UI components for SnapBase Streamlit interface.

Includes standardized headers, status badges, metric cards, confidence
indicators, and friendly empty states across all pages.
"""

from __future__ import annotations

from typing import Any, Optional
import streamlit as st

from config.settings import CONFIDENCE_THRESHOLD, DocumentStatus


def render_header(title: str, subtitle: str) -> None:
    """Render the centralized SnapBase brand gradient header banner.

    Args:
        title: Main page heading.
        subtitle: Explanatory page subtext.
    """
    html = f"""
    <div class="snapbase-banner">
        <h1>{title}</h1>
        <p>{subtitle}</p>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def get_status_badge_html(status: str) -> str:
    """Generate HTML snippet for styled status badges."""
    val = (status or "").lower()
    if val == DocumentStatus.PROCESSED.value:
        return '<span class="badge-processed">● Approved / Processed</span>'
    if val == DocumentStatus.REJECTED.value:
        return '<span class="badge-rejected">✖ Rejected</span>'
    return '<span class="badge-pending">▲ Pending Review</span>'


def render_metric_card(
    title: str, value: Any, subtitle: Optional[str] = None
) -> None:
    """Display a clean metric card container."""
    sub_html = (
        f'<div style="font-size: 0.85rem; color: #757575; margin-top: 4px;">{subtitle}</div>'
        if subtitle
        else ""
    )
    html = f"""
    <div class="snapbase-card">
        <div style="font-size: 0.85rem; font-weight: 600; color: #616161; text-transform: uppercase;">
            {title}
        </div>
        <div style="font-size: 2.1rem; font-weight: 800; color: #111111; margin-top: 4px;">
            {value}
        </div>
        {sub_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_confidence_indicator(confidence: float) -> str:
    """Return color-coded confidence badge HTML."""
    pct = int(confidence * 100)
    if confidence >= 0.85:
        color = "#2E7D32"
        bg = "#E8F5E9"
    elif confidence >= CONFIDENCE_THRESHOLD:
        color = "#F57C00"
        bg = "#FFF3E0"
    else:
        color = "#C62828"
        bg = "#FFEBEE"

    return (
        f'<span style="background-color: {bg}; color: {color}; '
        f'padding: 2px 8px; border-radius: 6px; font-weight: 700; font-size: 0.82rem;">'
        f'{pct}%</span>'
    )


def render_empty_state(message: str, hint: Optional[str] = None) -> None:
    """Render a clean white container indicating no records found."""
    hint_html = (
        f'<div style="color: #757575; font-size: 0.9rem; margin-top: 6px;">{hint}</div>'
        if hint
        else ""
    )
    html = f"""
    <div class="snapbase-card" style="text-align: center; padding: 40px 20px;">
        <div style="font-size: 2.5rem; margin-bottom: 10px;">📄</div>
        <div style="font-size: 1.15rem; font-weight: 700; color: #212121;">{message}</div>
        {hint_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

"""Records exploration, filtering, pagination, deletion, and data export.

Enables full-text field querying, status filtering, original image preview,
and multi-format export to CSV, Excel, and JSON.
"""

from __future__ import annotations

from datetime import datetime, time
import io
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd
import streamlit as st

from config.settings import DocumentStatus, load_schemas
from db.crud import delete_document, list_documents
from db.session import get_db_session, init_db
from ui.components import get_status_badge_html, render_empty_state, render_header
from ui.styles import inject_css

# Page Configuration
st.set_page_config(
    page_title="Records & Export | SnapBase",
    page_icon="📂",
    layout="wide",
)
inject_css()
init_db()

render_header(
    title="Document Records Repository",
    subtitle="Filter, search, review, and export ingested document attributes to CSV, Excel, or JSON",
)

schemas = load_schemas()

# Filter Controls Card
with st.container():
    st.markdown("### 🔍 Filters & Search")
    f_col1, f_col2, f_col3, f_col4 = st.columns(4)

    with f_col1:
        search_query = st.text_input("Search Text", placeholder="Merchant, ID, filename...")

    with f_col2:
        type_choices = ["all"] + list(schemas.keys())
        selected_type = st.selectbox("Document Type", type_choices)

    with f_col3:
        status_choices = ["all", "pending", "processed", "rejected"]
        selected_status = st.selectbox("Status", status_choices)

    with f_col4:
        sort_choice = st.selectbox(
            "Sort By", ["Created (Newest)", "Created (Oldest)", "Filename"]
        )
        sort_by = "created_at"
        sort_order = "desc" if "Newest" in sort_choice else "asc"
        if "Filename" in sort_choice:
            sort_by = "filename"
            sort_order = "asc"

# Pagination setup
page_size = 10
if "current_page" not in st.session_state:
    st.session_state["current_page"] = 1

with get_db_session() as session:
    docs, total_records = list_documents(
        session=session,
        doc_type=selected_type if selected_type != "all" else None,
        status=selected_status if selected_status != "all" else None,
        search_query=search_query if search_query.strip() else None,
        sort_by=sort_by,
        sort_order=sort_order,
        page=st.session_state["current_page"],
        page_size=page_size,
    )

total_pages = max(1, (total_records + page_size - 1) // page_size)

# Export Data Preparation
with get_db_session() as session:
    all_filtered_docs, _ = list_documents(
        session=session,
        doc_type=selected_type if selected_type != "all" else None,
        status=selected_status if selected_status != "all" else None,
        search_query=search_query if search_query.strip() else None,
        page=1,
        page_size=10000,
    )

export_rows: List[Dict[str, Any]] = []
for d in all_filtered_docs:
    row = {
        "id": d.id,
        "type": d.type,
        "filename": d.filename,
        "status": d.status,
        "is_edited": d.is_edited,
        "created_at": d.created_at.strftime("%Y-%m-%d %H:%M:%S") if d.created_at else "",
    }
    for f in d.fields:
        row[f"field_{f.key}"] = f.value
    export_rows.append(row)

export_df = pd.DataFrame(export_rows)

# Export Action Bar
if not export_df.empty:
    st.markdown("### 📥 Export Filtered Data")
    exp_col1, exp_col2, exp_col3, _ = st.columns([1, 1, 1, 2])

    with exp_col1:
        csv_bytes = export_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📄 Export CSV",
            data=csv_bytes,
            file_name="snapbase_records.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with exp_col2:
        excel_buffer = io.BytesIO()
        export_df.to_excel(excel_buffer, index=False, engine="openpyxl")
        st.download_button(
            "📊 Export Excel",
            data=excel_buffer.getvalue(),
            file_name="snapbase_records.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with exp_col3:
        json_str = export_df.to_json(orient="records", indent=2)
        st.download_button(
            "📦 Export JSON",
            data=json_str,
            file_name="snapbase_records.json",
            mime="application/json",
            use_container_width=True,
        )

st.divider()

# Records List
st.markdown(f"### 📋 Records Table ({total_records} matches)")

if not docs:
    render_empty_state(
        message="No documents match your query.",
        hint="Try clearing filters or uploading new documents.",
    )
else:
    for doc in docs:
        with st.expander(
            f"#{doc.id} | {doc.filename} ({doc.type}) — Status: {doc.status.upper()}"
        ):
            c_left, c_right = st.columns([1, 2])
            with c_left:
                if Path(doc.image_path).exists():
                    st.image(doc.image_path, caption=doc.filename, use_container_width=True)
                else:
                    st.caption("Image file missing on disk.")

            with c_right:
                st.markdown(
                    f"**Status:** {get_status_badge_html(doc.status)} &nbsp; "
                    f"**Edited:** {'Yes' if doc.is_edited else 'No'}",
                    unsafe_allow_html=True,
                )
                fields_dict = {f.key: f.value for f in doc.fields}
                st.write("**Extracted Fields:**")
                st.json(fields_dict)

                col_a1, col_a2 = st.columns(2)
                with col_a1:
                    if st.button("Edit / Verify in Review", key=f"rec_edit_{doc.id}"):
                        st.session_state["review_doc_id"] = doc.id
                        st.switch_page("pages/2_Review.py")
                with col_a2:
                    if st.button("🗑️ Delete Record", key=f"rec_del_{doc.id}"):
                        with get_db_session() as session:
                            delete_document(session, doc.id)
                        st.toast(f"Record #{doc.id} deleted.", icon="🗑️")
                        st.rerun()

    # Pagination controls
    st.markdown("<br>", unsafe_allow_html=True)
    p_col1, p_col2, p_col3 = st.columns([1, 2, 1])
    with p_col1:
        if st.session_state["current_page"] > 1:
            if st.button("⬅ Previous Page"):
                st.session_state["current_page"] -= 1
                st.rerun()
    with p_col2:
        st.markdown(
            f"<div style='text-align: center; color: #616161; font-weight: 600;'>"
            f"Page {st.session_state['current_page']} of {total_pages}</div>",
            unsafe_allow_html=True,
        )
    with p_col3:
        if st.session_state["current_page"] < total_pages:
            if st.button("Next Page ➡"):
                st.session_state["current_page"] += 1
                st.rerun()

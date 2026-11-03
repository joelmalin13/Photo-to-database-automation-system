"""Document upload and camera capture interface for SnapBase.

Supports single and batch processing, file validation, camera snapshots,
configurable document schema selection, and visual extraction progress.
"""

from __future__ import annotations

from typing import List, Tuple
from PIL import Image
import streamlit as st

from config.settings import GEMINI_API_KEY, load_schemas
from core.pipeline import batch_process_images, process_single_image
from db.session import init_db
from ui.components import get_status_badge_html, render_header
from ui.styles import inject_css

# Page Configuration
st.set_page_config(
    page_title="Ingest Documents | SnapBase",
    page_icon="📤",
    layout="wide",
)
inject_css()
init_db()

render_header(
    title="Document Ingestion",
    subtitle="Upload or capture document photographs to extract structured fields and detect duplicates",
)

schemas = load_schemas()
doc_type_options = {"Auto-detect": "auto"}
for key, defn in schemas.items():
    doc_type_options[defn.get("display_name", key)] = key

# Configuration row
col_cfg1, col_cfg2 = st.columns(2)
with col_cfg1:
    selected_type_label = st.selectbox(
        "Select Document Type",
        options=list(doc_type_options.keys()),
        index=0,
        help="Choose a specific schema or let SnapBase auto-detect from content.",
    )
    selected_doc_type = doc_type_options[selected_type_label]

with col_cfg2:
    engine_choices = ["Auto / Preferred", "Offline OCR (EasyOCR + Regex)"]
    if GEMINI_API_KEY:
        engine_choices.insert(1, "Gemini Vision API (Cloud)")
    selected_engine_label = st.selectbox("Extraction Engine", engine_choices)
    chosen_engine = None
    if "Gemini" in selected_engine_label:
        chosen_engine = "gemini"
    elif "Offline" in selected_engine_label:
        chosen_engine = "ocr"

# Ingestion Method Tabs
tab_upload, tab_camera = st.tabs(["📁 File Upload (Single / Batch)", "📷 Camera Capture"])

files_to_process: List[Tuple[bytes, str]] = []

with tab_upload:
    uploaded_files = st.file_uploader(
        "Upload document photos (JPG, PNG, WEBP — up to 10MB each)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
    )
    if uploaded_files:
        st.caption(f"Selected {len(uploaded_files)} file(s)")
        # Show mini thumbnails
        preview_cols = st.columns(min(len(uploaded_files), 4))
        for idx, file in enumerate(uploaded_files[:4]):
            with preview_cols[idx]:
                st.image(file, caption=file.name, use_container_width=True)
        if len(uploaded_files) > 4:
            st.caption(f"... and {len(uploaded_files) - 4} more files.")
        for f in uploaded_files:
            files_to_process.append((f.getvalue(), f.name))

with tab_camera:
    camera_photo = st.camera_input("Capture document using camera")
    if camera_photo:
        st.image(camera_photo, caption="Captured Document", width=300)
        files_to_process.append(
            (camera_photo.getvalue(), f"cam_capture_{camera_photo.id}.jpg")
        )

st.markdown("<br>", unsafe_allow_html=True)

if files_to_process:
    if st.button("🚀 Process & Extract Fields", type="primary", use_container_width=True):
        progress_bar = st.progress(0)
        status_text = st.empty()
        total_files = len(files_to_process)
        results = []

        # Consume generator for batch processing
        generator = batch_process_images(
            image_items=files_to_process,
            doc_type=selected_doc_type,
            preferred_engine=chosen_engine,
        )

        for i, res in enumerate(generator):
            results.append(res)
            pct = int(((i + 1) / total_files) * 100)
            progress_bar.progress(pct)
            status_text.text(f"Processed {i + 1} of {total_files}: {res.filename}")

        progress_bar.empty()
        status_text.empty()
        st.success(f"Processing finished! Processed {len(results)} document(s).")

        # Display results summary
        for res in results:
            with st.container():
                st.markdown(
                    f"""
                    <div class="snapbase-card">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <h4 style="margin: 0; color: #111111;">📄 {res.filename}</h4>
                            {get_status_badge_html(res.status)}
                        </div>
                        <p style="color: #616161; font-size: 0.88rem; margin: 6px 0;">
                            Type: <b>{res.doc_type}</b> | Engine: <b>{res.engine_used}</b>
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if res.is_duplicate:
                    st.warning(
                        f"⚠️ Duplicate Detected: {res.warnings[0]}", icon="⚠️"
                    )

                if res.warnings and not res.is_duplicate:
                    for w in res.warnings:
                        st.info(f"ℹ️ {w}")

                if res.error_message:
                    st.error(f"❌ Error: {res.error_message}")
                elif res.fields:
                    # Display extracted preview
                    fields_df = {
                        "Field": list(res.fields.keys()),
                        "Value": [str(v) if v is not None else "-" for v in res.fields.values()],
                        "Confidence": [
                            f"{int(res.confidences.get(k, 0) * 100)}%"
                            for k in res.fields.keys()
                        ],
                    }
                    st.dataframe(fields_df, use_container_width=True)

                    if res.document_id:
                        col_btn1, _ = st.columns([1, 4])
                        with col_btn1:
                            if st.button(
                                f"Review #{res.document_id}",
                                key=f"rev_{res.document_id}",
                            ):
                                st.session_state["review_doc_id"] = res.document_id
                                st.switch_page("pages/2_Review.py")

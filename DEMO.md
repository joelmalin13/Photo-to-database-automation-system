# SnapBase: 3-Minute Live Demonstration Script & Viva Q&A

This document provides a timed, step-by-step demonstration walkthrough for evaluators and answers 5 critical viva interview questions.

---

## ⏱️ 3-Minute Live Demo Script

### Step 1: System Startup & Portal Inspection (0:00 - 0:30)
1. Launch the application:
   ```bash
   streamlit run app.py
   ```
2. **Explain to Evaluator**:
   - Point out the unified brand banner: Black-to-red gradient (`#111111` -> `#C62828`).
   - Highlight the sidebar system readiness indicators: Database status, Gemini API status, and Offline OCR status.
   - Show that database tables are initialized idempotently on startup.

### Step 2: Upload & Automated Extraction (0:30 - 1:15)
1. Navigate to **"1. Ingest Documents"** (`pages/1_Upload.py`).
2. Set Document Type to **"Auto-detect"**.
3. Drag and drop `sample_data/receipt_1.png` and `sample_data/student_id_1.png`.
4. Click **"🚀 Process & Extract Fields"**.
5. **Explain to Evaluator**:
   - The batch generator streams results sequentially using Python's `yield` without blocking the UI thread.
   - OpenCV preprocessing performs EXIF orientation correction, deskewing, and Laplacian variance blur calculation.
   - SHA-256 cryptographic hash is generated to detect duplicate submissions.
   - Show the duplicate detection in action by re-uploading `receipt_1.png` to demonstrate the instant duplicate warning banner.

### Step 3: Human-in-the-Loop Review & Field Correction (1:15 - 2:00)
1. Click **"Review #1"** or navigate to **"2. Review & Verify"** (`pages/2_Review.py`).
2. **Explain to Evaluator**:
   - Point out the side-by-side verification view: Original photo on the left, editable form on the right.
   - Point out the color-coded confidence indicators next to each field:
     - Green (≥ 85%)
     - Amber (70% - 84%)
     - Red (< 70% with low-confidence alert box).
3. Make an intentional correction:
   - Change `vendor_name` from "ACME SUPERMARKET" to "ACME Express Supermarket".
4. Click **"✅ Approve / Save"**.
5. Observe the status badge transitioning from **"Pending Review"** (Amber) to **"Approved / Processed"** (Green), with the `is_edited` flag marked `True`.

### Step 4: Records Explorer, Full-Text Search & Export (2:00 - 2:35)
1. Navigate to **"3. Records & Export"** (`pages/3_Records.py`).
2. Filter by status **"processed"** or type **"receipt_invoice"**.
3. Type `"ACME"` into the search box to demonstrate dynamic full-text filtering.
4. Show the original image preview inside the record expander.
5. Click **"📄 Export CSV"**, **"📊 Export Excel"**, and **"📦 Export JSON"** to demonstrate multi-format data export.

### Step 5: Operational Analytics Dashboard (2:35 - 3:00)
1. Navigate to **"4. System Analytics"** (`pages/4_Dashboard.py`).
2. **Explain to Evaluator**:
   - Review the 4 high-level metric cards (Total Documents, Approved, Pending, Field Accuracy).
   - Show the 3 interactive Plotly visualizations styled with the custom red/black/gray palette:
     1. Document Status Distribution (Donut chart).
     2. Document Volume by Schema Type (Bar chart).
     3. Automation Efficiency (Zero-Edit Perfect vs User Corrected).

---

## 🎓 Top 5 Viva Questions & Short Answers

### Q1: How does SnapBase handle image duplicates without re-running expensive OCR or AI models?
> **Answer:** Before executing preprocessing or calling any extraction engine, SnapBase calculates a SHA-256 cryptographic digest of the raw image bytes. It queries the `documents` table by indexed `image_hash`. If a match is found, processing halts immediately, and the system returns the existing document record alongside a duplicate warning link, saving computation and API quota.

### Q2: Why did you implement an Abstract Base Class (`BaseExtractor`) instead of directly calling Gemini or EasyOCR?
> **Answer:** We implemented `BaseExtractor` using Python's `abc.ABC` to satisfy the Open-Closed and Dependency Inversion Principles. The application interacts solely with the abstract polymorphic `extract()` interface. This allows seamless switching between cloud vision and offline OCR via a factory function (`get_extractor()`) and enables automated fallback when external APIs fail or credentials are absent.

### Q3: How is database concurrency and transaction safety handled?
> **Answer:** Database interactions are managed via a custom context manager `get_db_session()` in `db/session.py`. It wraps transactions in a `try...except...finally` block that automatically commits upon success, performs an explicit rollback if any exception occurs, and guarantees session closure in the `finally` block to prevent SQLite connection leaks.

### Q4: Why did you use Python generators for batch processing instead of a simple list?
> **Answer:** `batch_process_images` is implemented as a generator using `yield`. In document automation workflows, images can be large (up to 10MB each). Yielding individual `ProcessResult` objects sequentially allows Streamlit to update the progress bar in real time, keeps memory consumption low, and prevents UI thread freezing during large batch jobs.

### Q5: How does the offline OCR engine parse key-value fields from raw OCR text lines?
> **Answer:** The offline extractor uses a schema-driven regex engine. In `config/schemas.json`, each field defines ordered regular expressions. The engine scans both multiline document text and individual text bounding boxes, capturing target groups (dates, float amounts, names). Confidence scores are dynamically weighted based on OCR character recognition quality and pattern specificity.

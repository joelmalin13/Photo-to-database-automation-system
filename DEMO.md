# SnapBase: 3-Minute Live Demonstration Script & Viva Q&A

This document provides a timed, step-by-step demonstration walkthrough for evaluators and answers 5 critical viva interview questions for the upgraded FastAPI + HTMX full-stack architecture.

---

## 3-Minute Live Demo Script

### Step 1: System Startup & Portal Inspection (0:00 - 0:30)
1. Launch the application:
   ```bash
   uvicorn app.main:app --reload
   ```
2. Open `http://localhost:8000` in the browser.
3. **Explain to Evaluator**:
   - Point out the unified SaaS design system: Inter font, clean white backgrounds, deep black navigation bar, and single crimson red accent (`#C62828`).
   - Highlight the top bar engine indicator pill: Displays active extraction engine (Gemini or Offline OCR) and connection status.
   - Point out the KPI summary cards with "No data yet" zero-state protection and Chart.js analytics.
   - Show the interactive Swagger API documentation at `http://localhost:8000/docs`.

### Step 2: Ingest Documents & Duplicate Detection (0:30 - 1:15)
1. Navigate to **"Upload Photos"** (`/upload`).
2. Set Document Type to **"Auto-detect"**.
3. Drag and drop `sample_data/receipt_1.png` and `sample_data/student_id_1.png`.
4. Click **"Ingest & Process Documents"**.
5. **Explain to Evaluator**:
   - Ingestion is handled via an asynchronous FastAPI service layer (`DocumentService.ingest_upload`).
   - OpenCV preprocessing performs EXIF orientation correction, deskewing, and Laplacian variance blur calculation.
   - SHA-256 cryptographic hash is computed to immediately detect duplicate submissions.
   - Demonstrate duplicate prevention: Re-upload `receipt_1.png` to show the duplicate warning badge pointing to the existing record ID.

### Step 3: Human-in-the-Loop Review & Field Correction (1:15 - 2:00)
1. Click **"Review"** on an ingested document or navigate to `/review`.
2. **Explain to Evaluator**:
   - Highlight the split-screen verification interface: Pannable and zoomable image viewer on the left (with zoom in/out, reset, and 90-degree rotate controls), and editable form on the right.
   - Color-coded confidence indicators next to each field:
     - Green (>= 85%)
     - Amber (70% - 84%)
     - Red (< 70% with low-confidence alert box).
   - Point out the keyboard shortcuts (`Ctrl+Enter` to approve, `Esc` to reject).
3. Make an intentional field edit (e.g., adjust vendor name or total amount) and add a line item.
4. Click **"Approve Document"** (or press `Ctrl+Enter`).
5. Observe the status badge transitioning from **"Pending"** (Amber) to **"Approved"** (Green) with the `is_edited` flag marked `True`.

### Step 4: Records Repository, Full-Text Search & Multi-Format Export (2:00 - 2:35)
1. Navigate to **"Records Repository"** (`/records`).
2. Click the status filter chip **"Approved"** or type into the search box.
3. **Explain to Evaluator**:
   - HTMX performs live partial page swaps (`/partials/records-table`) with a debounced 300ms trigger, delivering an SPA feel without a heavy frontend framework.
   - Click a document row to open the slide-over inspection drawer (`/partials/drawer/{id}`) showing full field extractions, line items, and quick action buttons.
   - Click **"Export Repository"** to demonstrate multi-format download: **CSV**, **Excel (.xlsx)**, and **JSON**.

### Step 5: System Settings & Analytics (2:35 - 3:00)
1. Navigate to **"System Settings"** (`/settings`).
2. **Explain to Evaluator**:
   - Point out the extraction engine toggle (Google Gemini vs Offline OCR).
   - Explain the confidence threshold slider that gates automatic human review routing.
   - Navigate to `/` (Dashboard) to show the updated Chart.js donut chart (status split), document types bar chart, and time-series line chart reflecting the newly approved records.

---

## Top 5 Viva Questions & Short Answers

### Q1: Why did you migrate from Streamlit to FastAPI + HTMX?
> **Answer:** Streamlit reruns the entire Python script on every user interaction, which causes high server memory overhead, prevents granular partial UI updates, and limits architectural decoupling. Migrating to FastAPI + HTMX established a true production-grade architecture:
> 1. A dedicated service layer separating business logic from routing.
> 2. Open standard REST API endpoints with auto-generated OpenAPI/Swagger documentation (`/docs`).
> 3. Sub-50ms HTMX partial swaps for search and slide-over drawers without needing a complex Node/React build pipeline.
> 4. True asynchronous concurrency and background processing.

### Q2: How does SnapBase handle image duplicates without re-running expensive OCR or AI models?
> **Answer:** Before executing preprocessing or calling any extraction engine, SnapBase calculates a SHA-256 cryptographic digest of the raw image bytes. It queries the `documents` table by indexed `image_hash`. If a match is found, processing halts immediately, and the system returns the existing document record alongside a duplicate flag, saving computation and API quota.

### Q3: Why did you implement an Abstract Base Class (`BaseExtractor`) instead of directly calling Gemini or EasyOCR?
> **Answer:** We implemented `BaseExtractor` using Python's `abc.ABC` to satisfy the Open-Closed and Dependency Inversion Principles. The application interacts solely with the abstract polymorphic `extract()` interface. This allows seamless switching between cloud vision and offline OCR via a factory function (`get_extractor()`) and enables automated fallback when external APIs fail or credentials are absent.

### Q4: How is database concurrency and transaction safety handled in the FastAPI service layer?
> **Answer:** Database interactions are managed via FastAPI's `Depends(get_db)` dependency and a custom context manager `get_db_session()` in `db/session.py`. Both implement the Unit of Work pattern: wrapping transactions in a `try...except...finally` block that automatically commits upon success, performs an explicit rollback if any exception occurs, and guarantees session closure in the `finally` block to prevent SQLite connection leaks.

### Q5: How does the offline OCR engine parse key-value fields from raw OCR text lines?
> **Answer:** The offline extractor uses a schema-driven regex engine. In `config/schemas.json`, each field defines ordered regular expressions. The engine scans both multiline document text and individual text bounding boxes, capturing target groups (dates, float amounts, names). Confidence scores are dynamically weighted based on OCR character recognition quality and pattern specificity.

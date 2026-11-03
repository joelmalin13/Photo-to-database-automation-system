# SnapBase: Live Demonstration Script & Viva Defense Guide

This document provides a timed, step-by-step demonstration walkthrough for evaluators, judges, and instructors, followed by core viva interview defense questions for the SnapBase photo-to-database automation system.

---

## 3-Minute Live Demonstration Walkthrough

### Step 1: System Startup & Architecture Verification (0:00 - 0:30)
1. Launch the server from terminal:
   ```bash
   uvicorn app.main:app --reload
   ```
2. Open `http://localhost:8000` in the browser.
3. **Key Points for Evaluators**:
   - Point out the unified SaaS design system: Inter typography, white canvas, subtle gray borders, deep-black header (`#111111`), and crimson red accent (`#C62828`). Zero emojis anywhere in the system.
   - Point out the top bar status pills:
     - **Database Health**: Shows `MySQL (Connected)` or `SQLite (Fallback Active)`. Explain the zero-downtime resilience: if MySQL is unreachable, the server auto-falls back to SQLite without crashing.
     - **OCR Engine**: Shows default `EasyOCR` (with word bounding boxes and confidence).
   - Show the interactive Swagger API documentation at `http://localhost:8000/docs`.

---

### Step 2: Document Ingestion & Duplicate Detection (0:30 - 1:00)
1. Navigate to **"Upload Documents"** (`/upload`).
2. Select Document Type: **"Receipts / Bills"** (or Student Marksheet / Business Card).
3. Drag and drop `sample_data/receipt_1.png` and click **"Ingest & Process Documents"**.
4. **Key Points for Evaluators**:
   - Instant SHA-256 cryptographic image hashing.
   - OpenCV preprocessing handles EXIF auto-rotation, deskewing, and Laplacian variance blur calculation.
   - **Demonstrate Duplicate Prevention**: Re-upload `receipt_1.png`. The system instantly detects the duplicate hash, prevents duplicate database insertion, and provides a direct link to the existing document record.

---

### Step 3: Interactive Image Processing Playground (1:00 - 1:30)
1. Navigate to **"Image Processing"** (`/image-processing`).
2. Upload a sample document.
3. Toggle enhancement controls:
   - **Contrast (CLAHE)**: Enhances faded or uneven thermal receipt print.
   - **Denoise & Sharpen**: Clarifies fine lines and text edges.
   - **Adaptive / Otsu Thresholding**: Converts document into high-contrast binary text.
4. Click **"Run OCR"** or **"Retry OCR after enhancement"**.
5. **Key Points for Evaluators**:
   - Show the side-by-side original vs. processed image viewer.
   - Point out the extracted text box and the interactive per-word confidence pill tags showing individual recognition certainty.

---

### Step 4: Human-in-the-Loop Review & Data Promotion (1:30 - 2:15)
1. Navigate to **"Review"** (`/review`) and select the pending document.
2. **Key Points for Evaluators**:
   - **Split View**: Zoomable, pannable, rotatable image canvas on the left; editable structured form on the right.
   - **Confidence Meters**: Fields scoring below the threshold are visually highlighted in amber with confidence percentages.
   - **The Strict Integrity Rule**: Highlight that raw OCR data is stored only in the generic staging table `documents` with status `processed`. The business table (`receipts`, `students`, or `business_cards`) remains empty until approval!
3. Review and edit any field (e.g., adjust shop name or total amount).
4. Click **"Approve Document"** (or press `Ctrl+Enter`).
5. **Observe**: The document status transitions to `verified`, and the confirmed record is created in the normalized relational tables.

---

### Step 5: Database Explorer, Analytics & Formatted Reports (2:15 - 3:00)
1. **Records Explorer (`/records`)**:
   - Demonstrate HTMX live search and category filter chips (`Receipts`, `Students`, `Business Cards`).
   - Click a record to open the detailed inspector modal.
2. **Analytics Dashboard (`/analytics`)**:
   - View real-time Chart.js charts: Category Distribution (Donut), Ingestion Trend (Line), Top Merchants by Total Spend (Bar), and Student Performance Comparison (Bar).
3. **Export Reports (`/reports`)**:
   - Download the **Excel (`.xlsx`)** report. Open or highlight that OpenPyXL formats the spreadsheet with dark header styling, bold summary totals, and auto-fitted columns.
   - Highlight CSV and JSON download options.

---

## Top 5 Viva Defense Questions & Answers

### Q1: How does SnapBase guarantee data integrity when OCR text is noisy or inaccurate?
> **Answer:** SnapBase enforces a strict separation between raw OCR output and confirmed business data. All ingested images and their extracted text are initially quarantined in a staging table (`documents`) with status `processed`. Confirmed domain tables (`receipts`, `receipt_items`, `students`, `marks`, `business_cards`) are only populated when a human operator verifies and approves the record. If an image is unreadable or malformed, it can be rejected, leaving business ledgers untainted.

### Q2: What is the architectural difference between OCR Confidence and Field Extraction Accuracy?
> **Answer:** They measure two different stages of the pipeline:
> 1. **OCR Confidence** is a deep-learning statistical metric from the OCR model (e.g. EasyOCR) reflecting its internal probability that character glyphs match the text strings.
> 2. **Field Extraction Accuracy** measures end-to-end semantic correctness: whether the parsed, cleaned, and normalized key-value pairs (e.g. `shop_name`, `total_amount`, `usn`) match the expected ground-truth data. High character confidence doesn't guarantee correct layout mapping, whereas robust regex and Pandas post-processing can often recover 100% accurate fields even from slightly noisy OCR text.

### Q3: How does the system achieve zero downtime if the MySQL database server is unreachable?
> **Answer:** In `db/session.py`, the engine initialization performs an active ping against the configured MySQL URI. If MySQL is unreachable (network timeout, authentication failure, or daemon offline), an exception is caught, a warning is logged, and the engine automatically falls back to a local SQLite database (`data/snapbase.db`). The system never crashes on startup, and the current connection status is clearly reflected in the top bar and Settings page.

### Q4: Why did you build the Image Processing Playground?
> **Answer:** Real-world photos often suffer from poor lighting, thermal fade, motion blur, or uneven perspective. Rather than failing permanently, the Image Processing playground gives users interactive computer vision controls (CLAHE contrast, Otsu adaptive thresholding, Gaussian blur, Laplacian denoising, morphological sharpening, and deskewing) with immediate side-by-side feedback. Users can test enhancements and re-run OCR on the clarified image directly in the browser.

### Q5: How are duplicates detected, and what is the computational overhead?
> **Answer:** Duplicate detection uses SHA-256 cryptographic hashing on the raw image byte stream during initial file validation. Computing the SHA-256 hash takes less than 15 milliseconds for a typical 2MB photo. The database enforces a `UNIQUE` constraint on `image_hash`. When a duplicate is detected, the pipeline halts further expensive OCR inference and returns the existing document record with an informational notice.

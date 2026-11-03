# SnapBase: Exhibition & Viva Presentation Outline
## Technical Project Demonstration & Defense Guide

---

### Slide 1: Title & Overview
- **Project Name:** SnapBase - Intelligent Photo-to-Database Automation System
- **Category:** Computer Vision, Web Engineering, and Enterprise Database Systems
- **Core Technology:** FastAPI, SQLAlchemy 2.0, EasyOCR/Tesseract, OpenCV, Pandas, Tailwind CSS, Alpine.js, HTMX, Chart.js, OpenPyXL
- **Key Takeaway:** An automated, self-hosted document digitization platform that replaces slow manual typing with instant optical recognition, robust computer vision preprocessing, and strict human-in-the-loop database promotion.

---

### Slide 2: The Problem Space
- **Enterprise Pain Point:** Organizations process thousands of invoices, student marksheets, and business cards manually.
- **Latency & Error Rate:** Manual data entry incurs 2-5 minutes per document with an average typing error rate of 4-8%.
- **The "Noisy OCR" Pitfall:** Basic OCR projects dump unverified, corrupted text directly into production databases, causing corrupt records, invalid sums, and broken foreign keys.
- **Duplicate Document Waste:** Accidental re-submission of identical invoices creates phantom liabilities in enterprise ledgers.

---

### Slide 3: SnapBase Innovation Pillars
1. **Unverified Data Isolation:**
   - Raw OCR output is strictly quarantined in a staging status (`processed`).
   - Only upon authorized human review does data populate confirmed normalized tables (`receipts`, `students`, `business_cards`).
2. **Deterministic Duplicate Prevention:**
   - Pre-computation of SHA-256 hashes blocks identical document re-ingestion in under 15ms.
3. **Resilient Database Architecture:**
   - Primary: MySQL 8.0+ with connection pooling and relational integrity.
   - Automatic Zero-Downtime Fallback: Detects unreachable MySQL and instantly fails over to local SQLite without terminating the server.
4. **Interactive Computer Vision Playground:**
   - Operators can interactively adjust CLAHE contrast, Otsu adaptive thresholding, Gaussian blur, and perspective deskewing with real-time side-by-side previews before retrying OCR.
5. **Multi-Domain Document Awareness:**
   - Specialized regex extraction rules and Pydantic schemas for Receipts/Bills, Student Marksheets, and Business Cards.

---

### Slide 4: System Architecture & Technical Flow
```
[ Browser (Tailwind + HTMX) ]
              │
              ▼
[ FastAPI Async REST API & Jinja2 Template Layer ]
              │
    ┌─────────┴─────────┐
    ▼                   ▼
[ OpenCV Filters ]  [ EasyOCR / Tesseract ]
    │                   │
    └─────────┬─────────┘
              ▼
    [ Pandas Data Cleaner (Dates, Phones, Amounts) ]
              │
              ▼
    [ Pydantic Schema Validation & Confidence Adjustment ]
              │
              ▼
    [ SQLAlchemy 2.0 Resilient Database Engine ]
         ├── Primary: MySQL 8.0+ (photo_automation)
         └── Fallback: SQLite3 (data/snapbase.db)
```

---

### Slide 5: Live Demonstration Walkthrough Script

#### Phase 1: Ingestion & Duplicate Protection (`/upload`)
- **Action:** Drag and drop a receipt (`sample_data/receipt_1.png`).
- **Explanation to Judges:** Watch the instantaneous SHA-256 computation and progress feedback. Notice that re-uploading the exact same image triggers the duplicate detector immediately with a notification pointing to the existing record ID.

#### Phase 2: Interactive Image Processing Playground (`/image-processing`)
- **Action:** Upload a low-contrast or noisy document. Adjust the **CLAHE Contrast**, **Sharpen**, and **Denoise** toggles. Click **Run OCR**.
- **Explanation to Judges:** Demonstrate how computer vision filters clarify faded ink or thermal receipt text, showing extracted text and per-word confidence tags.

#### Phase 3: Human Verification & Split-View Review (`/review`)
- **Action:** Open the document in the split-view verification screen.
- **Explanation to Judges:** On the left is the zoomable, pannable image viewer. On the right is the structured form. Point out confidence meters—fields below the 70% threshold are highlighted in amber. Demonstrate keyboard shortcuts (`Ctrl+Enter` to approve, `Esc` to reject).
- **Core Principle:** Show that the `receipts` table in the database is currently empty until the "Approve" button is pressed.

#### Phase 4: Database Records & Filter Drawer (`/records`)
- **Action:** Show the records table with live HTMX search, category filter chips (Receipts, Marksheets, Business Cards), and detailed record views.

#### Phase 5: Live Analytics Dashboard (`/analytics`)
- **Action:** Showcase real-time Chart.js visualizations:
  - Document Category Breakdown (Donut)
  - Success vs. Failure (Bar)
  - Ingestion Trends over Time (Line)
  - Top Merchants by Spend (Bar)
  - Student Marks & Performance (Horizontal Bar)

#### Phase 6: Report Generation (`/reports`)
- **Action:** Download the Excel report (`.xlsx`). Open it or highlight that OpenPyXL formats the spreadsheet with dark header styling, auto-fitted column widths, and an executive summary sheet.

#### Phase 7: System Settings & Health Diagnostic (`/settings`)
- **Action:** Navigate to Settings. Point out the live database badge showing either `MySQL (Connected)` or `SQLite (Fallback Active)`, engine selection radios, and confidence threshold sliders.

---

### Slide 6: Evaluation & Benchmark Results
Highlight results from `docs/evaluation.md`:
- **Dataset:** 15 labelled synthetic documents (5 receipts, 5 marksheets, 5 business cards).
- **Key Metric Distinction:**
  - **OCR Confidence (58.2% avg):** Raw character-level probability from deep learning tensors.
  - **Field-Level Extraction Accuracy (36.2% avg):** Semantic correctness of business fields mapped against ground truth.
- Emphasize how Pandas cleaning recovers accurate data even when raw OCR confidence fluctuates.

---

### Slide 7: Frequently Asked Questions & Viva Defense

**Q1: Why did you choose FastAPI over Streamlit or Django?**
> *Answer:* FastAPI provides high-throughput asynchronous execution, native OpenAPI documentation (`/docs`), complete UI styling flexibility using Tailwind CSS and HTMX without frontend Node build dependencies, and strict separation between the API service layer and presentation.

**Q2: How does SnapBase prevent saving corrupt OCR data into production tables?**
> *Answer:* By architectural design, all ingested files are stored only in a generic staging table (`documents`). Dedicated business tables (`receipts`, `receipt_items`, `students`, `marks`, `business_cards`) are only populated when a human operator verifies and approves the record.

**Q3: What happens if the MySQL server crashes during operation?**
> *Answer:* The database initialization engine (`db/session.py`) performs an active ping. If MySQL is unreachable, it logs a warning, flags fallback status, and binds to a local SQLite database, ensuring zero downtime.

**Q4: How does the system handle blurry photos?**
> *Answer:* During preprocessing, we compute the Laplacian variance of the image. Images scoring below 100.0 are automatically flagged as blurry, prompting the user with an optimization warning. Operators can also route the image through the Image Processing page to apply sharpening and CLAHE before re-running OCR.

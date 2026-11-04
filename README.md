# Photo to Database Automation System
### Turn a photo of a receipt into clean, searchable data

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/Database-SQLite-blue.svg)](https://www.sqlite.org/)
[![EasyOCR](https://img.shields.io/badge/OCR-EasyOCR-brightgreen.svg)](https://github.com/JaidedAI/EasyOCR)
[![OpenCV](https://img.shields.io/badge/Vision-OpenCV-red.svg)](https://opencv.org/)

**100% Python | OCR + SQLite | You Verify Every Record**  
*KLE Technological University, Hubballi — B.E. Computer Science & Engineering (2025-2026)*

---

## Overview

The **Photo to Database Automation System** turns photos of physical receipts into clean, searchable, relational database records. Built with FastAPI, SQLite, OpenCV, EasyOCR, Pandas, and Tailwind CSS/HTMX, the system replaces slow, error-prone manual data entry with an automated 6-step pipeline backed by human-in-the-loop verification.

### 6-Step Pipeline (Slide 3)
1. **Upload**: Drag-and-drop or 1-click ABC MART demo receipt.
2. **Clean**: OpenCV preprocessing (grayscale, noise reduction, deskew, adaptive thresholding).
3. **Read**: EasyOCR text extraction with bounding boxes and per-word confidence.
4. **Find**: Regex pattern extraction (shop_name, date, phone, email, pincode, 	otal_amount).
5. **Check**: Human-in-the-loop split-screen review (● Looks good vs ● Please check amber flags, and auto-check validation rules).
6. **Save**: Stored in SQLite database table 
eceipts with Spending Dashboard, 'Ask Your Receipts' natural language queries, and 1-click Excel export.

---

## Key System Pillars

1. **Enterprise Database Architecture (MySQL 8.0+ with Zero-Downtime Fallback)**:
   - Primary database: MySQL 8.0+ via `mysql-connector-python` using connection pooling.
   - Resilient startup: If MySQL is unreachable, the system logs a diagnostic message, reflects fallback status on the Settings page, and automatically fails over to a local SQLite database (`data/snapbase.db`) without crashing.
   - Tests run in an isolated in-memory SQLite database (`sqlite:///:memory:`).
2. **Strict Data Integrity Boundary**:
   - Unverified raw OCR output is never directly inserted into confirmed business tables.
   - Ingested records remain in staging (`documents` table with status `processed`).
   - Only upon human verification are records promoted to confirmed tables: `receipts` (with line items), `students` (with marks), or `business_cards`.
3. **Pluggable OCR Architecture**:
   - **Default Engine**: EasyOCR (character recognition, bounding boxes, word-level confidence).
   - **Optional Engine**: Tesseract OCR (with automated EasyOCR fallback if the system binary is missing).
   - **Optional Engine**: Google Gemini Multimodal Vision API.
4. **Multi-Domain Document Awareness**:
   - **Receipts / Invoices**: Merchant name, invoice/receipt number, date, phone, line items (qty, price, amount), subtotal, tax, total amount.
   - **Student Marksheets**: Student name, USN/registration number, college, semester, subject rows (code, marks, max), total, percentage, pass/fail result.
   - **Business Cards**: Person name, job title, company, phone, email, website, postal address.
5. **Interactive Computer Vision Playground (`/image-processing`)**:
   - Side-by-side interactive visual comparison between the original photo and processed outputs.
   - Real-time adjustment controls: Grayscale, Gaussian Blur, Laplacian Denoising, Morphological Sharpening, Otsu/Adaptive Thresholding, CLAHE Contrast, Auto-Deskew, and Perspective Correction.
   - On-demand **Run OCR** and **Retry OCR after enhancement** buttons with per-word confidence tags.
6. **Pandas Data Cleaning Engine**:
   - Automated whitespace collapse, date standardization to ISO-8601 (`YYYY-MM-DD`), phone number sanitization, email format validation, and currency parsing.
   - Suspicious and low-confidence field flags preventing erroneous business ledger updates.
7. **Human-in-the-Loop Split-View Review (`/review`)**:
   - Interactive zoomable and pannable image viewer on the left; structured editable form on the right.
   - Confidence meters with visual warnings for fields scoring under 70%.
   - Keyboard shortcuts: `Ctrl+Enter` to approve and promote to confirmed business tables; `Esc` to reject.
8. **Live Records Explorer & Formatted Exports (`/records` & `/reports`)**:
   - HTMX-powered live search and category filtering chips.
   - Styled Excel (`.xlsx`) generated using OpenPyXL with dark header styling and auto-fitted columns.
   - CSV, JSON, and text executive summary exports.

---

## System Architecture

```mermaid
flowchart TD
    subgraph Client["Client Tier (FastAPI + Jinja2 Templates)"]
        UI["Tailwind CSS + Alpine.js + HTMX + Chart.js (No Node build required)"]
    end

    subgraph Server["Application Server (FastAPI + Uvicorn)"]
        RouterPages["HTML Page Router (app/routers/pages.py)"]
        RouterAPI["REST API Router (app/routers/api.py)"]
        
        subgraph Services["Service Layer"]
            DocService["DocumentService (Lifecycle & Promotion)"]
            ImgService["ImageProcessingService (Playground Previews)"]
            StatsService["StatsService (Metrics & Aggregations)"]
            ReportService["ReportService (OpenPyXL Excel & CSV)"]
        end
        
        RouterPages --> DocService
        RouterPages --> StatsService
        RouterAPI --> DocService
        RouterAPI --> ImgService
        RouterAPI --> StatsService
        RouterAPI --> ReportService
    end

    subgraph Core["Core Processing Pipeline"]
        Preprocess["OpenCV Preprocessor (CLAHE, Denoise, Blur Check, Deskew)"]
        Hasher["SHA-256 Duplicate Detector"]
        OCREngines["Extractor Factory (EasyOCR / Tesseract / Gemini)"]
        PandasCleaner["Pandas Data Cleaner (Dates, Phones, Amounts)"]
        Validators["Pydantic Schema Validation & Confidence Adjustment"]
        
        Hasher --> Preprocess --> OCREngines --> PandasCleaner --> Validators
    end

    subgraph Data["Database Persistence Layer"]
        ResilientEngine["Resilient Connection Router"]
        MySQL[("MySQL 8.0+ Primary\nphoto_automation")]
        SQLiteFallback[("SQLite 3 Fallback\ndata/snapbase.db")]
        
        ResilientEngine -->|Active Ping OK| MySQL
        ResilientEngine -->|Connection Fails| SQLiteFallback
    end

    DocService --> Core
    DocService --> ResilientEngine
    StatsService --> ResilientEngine
    ReportService --> ResilientEngine
```

---

## Database Schema (Normalized)

Defined in `database/schema.sql` and implemented via SQLAlchemy 2.0 ORM:

```mermaid
erDiagram
    USERS ||--o{ DOCUMENTS : "uploads"
    DOCUMENTS ||--o| RECEIPTS : "promotes upon approval"
    DOCUMENTS ||--o| STUDENTS : "promotes upon approval"
    DOCUMENTS ||--o| BUSINESS_CARDS : "promotes upon approval"
    DOCUMENTS ||--o{ PROCESSING_HISTORY : "audit log"
    RECEIPTS ||--o{ RECEIPT_ITEMS : "has line items"
    STUDENTS ||--o{ MARKS : "has course marks"
```

1. **`users`**: Authentication credentials and user roles.
2. **`documents`**: Ingested image path, unique SHA-256 hash, category, raw OCR text, average confidence, status (`uploaded`, `processed`, `verified`, `rejected`, `failed`), and staging JSON payload.
3. **`receipts` & `receipt_items`**: Confirmed vendor transactions, tax, subtotal, total amount, and line items.
4. **`students` & `marks`**: Confirmed student identity, USN, college, semester, percentage, result, and individual course marks.
5. **`business_cards`**: Confirmed professional contact cards.
6. **`processing_history`**: Audit trail logging every execution step, millisecond duration, and status transition.

---

## Application Pages Walkthrough

1. **Home Dashboard (`/`)**: Operational KPI cards (documents, approved, pending, accuracy), line chart of ingestion trends, donut chart of document distribution, and recent activity logs.
2. **Upload Documents (`/upload`)**: Drag-and-drop batch upload supporting multiple files, webcam snapshot capture, category selector, and SHA-256 duplicate detection.
3. **Image Processing Playground (`/image-processing`)**: Side-by-side original vs. filtered image view, enhancement sliders (CLAHE, thresholding, blur, sharpen, deskew), and on-demand OCR re-testing.
4. **Extracted Information Review (`/review`)**: Human-in-the-loop split screen with pannable/zoomable canvas on the left, editable form fields with confidence meters on the right, and approve/reject actions.
5. **Database Records (`/records`)**: HTMX live search, category filter chips (`receipts`, `students`, `business_cards`), sortable columns, and detailed record views.
6. **Analytics (`/analytics`)**: Deep data analytics powered by Chart.js (monthly trends, category split, top merchants by spend, student score distribution).
7. **Export Reports (`/reports`)**: Date and category filtered report generator exporting to OpenPyXL-formatted Excel spreadsheets, CSV, and summary reports.
8. **Settings (`/settings`)**: Live database health indicator (`MySQL` or `SQLite Fallback`), OCR engine selection radio group, and confidence threshold configurations.

---

## Installation & Setup

### Prerequisites
- Python 3.10+
- (Optional) MySQL Server 8.0+ (If MySQL is not installed or unreachable, SnapBase automatically defaults to local SQLite).
- (Optional) Tesseract OCR (If uninstalled, SnapBase automatically defaults to EasyOCR).

### 1. Clone the Repository
```bash
git clone https://github.com/joelmalin13/Photo-to-database-automation-system.git
cd Photo-to-database-automation-system
```

### 2. Set Up Virtual Environment & Dependencies
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure Database (.env)
Create or edit `.env` in the project root:
```env
# Primary MySQL Configuration
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=photo_automation

DATABASE_URL=mysql+mysqlconnector://root:your_password@localhost:3306/photo_automation

# OCR Preferences
DEFAULT_ENGINE=ocr
CONFIDENCE_THRESHOLD=0.70
```

### 4. Initialize MySQL Database (Optional)
If using MySQL, execute the DDL schema script:
```bash
mysql -u root -p < database/schema.sql
```
*Note: If MySQL is not running, no setup is required! SnapBase will detect this and automatically initialize `data/snapbase.db` using SQLite.*

---

## Running the Application

Start the FastAPI application via Uvicorn:
```bash
uvicorn app.main:app --reload --port 8000
```
Open your browser at:
- Web Application: **http://127.0.0.1:8000**
- Interactive Swagger API Documentation: **http://127.0.0.1:8000/docs**
- ReDoc API Documentation: **http://127.0.0.1:8000/redoc**

---

## Evaluation Benchmark

Run the synthetic evaluation benchmark on the 15 labelled documents (5 receipts, 5 marksheets, 5 business cards):
```bash
python evaluate.py
```
This produces the evaluation report in `docs/evaluation.md`, measuring:
- **Average OCR Confidence**: The optical character recognition model's internal certainty.
- **Field-Level Extraction Accuracy**: Percentage of business fields matching ground truth after normalization.

---

## Running the Test Suite

SnapBase includes 52 automated tests covering the API, service layer, image processing, CRUD operations, database resilience, and schema validations:
```bash
python -m pytest tests/ -v
```

---

## Running with Docker

Build and run using Docker:
```bash
docker build -t snapbase .
docker run -p 8000:8000 snapbase
```

---

## Design System Specifications
- **Typography:** Inter (via Google Fonts).
- **Color Palette:** Pure white background (`#FFFFFF`), near-black text (`#111827`), subtle gray borders (`#E5E7EB`), red primary accent (`#C62828`), dark top bar/sidebar header (`#111111`).
- **Icons:** Lucide SVG icons (zero emojis).
- **Responsive:** Mobile-first layout with collapsible navigation sidebar.

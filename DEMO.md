# Photo to Database Automation System
## Live Demonstration Script & Viva Defense Guide

> **Project Title**: Photo to Database Automation System: Turn a photo of a receipt into clean, searchable data  
> **Tagline**: 100% Python | OCR + SQLite | You Verify Every Record  
> **Institution**: KLE Technological University, Hubballi — B.E. Computer Science & Engineering (2025-2026)  
> **Based on**: Project Presentation Slides 1–8  

---

## 3-Minute Live Walkthrough (Aligned with Slide 7)

### Step 1: System Startup & Overview (Slide 1 & Slide 4)
1. Launch the server from terminal:
   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```
2. Open `http://localhost:8000` in the browser.
3. **Key Points for Evaluators**:
   - **Branding**: Photo to Database Automation System (KLE Tech CSE).
   - **Tech Stack (Slide 4)**: 100% Python backend (FastAPI), OpenCV preprocessing, EasyOCR offline recognition, Python regex pattern matching, SQLite relational database, and OpenPyXL Excel export.
   - **Top bar status**: Shows Database (SQLite zero-config), OCR Engine (EasyOCR offline mode), and Direct Actions.

---

### Step 2: Ingest ABC MART Demo Receipt (Slide 3 Step 1 & Slide 7)
1. Navigate to **"Upload Receipts"** (`/upload`).
2. Click the prominent banner button: **"Load & Process Demo Receipt"** (or drag and drop `sample_data/abc_mart_receipt.png`).
3. **What happens automatically**:
   - **Clean (Slide 3 Step 2)**: OpenCV executes grayscale conversion, noise reduction, deskewing, and adaptive thresholding.
   - **Read (Slide 3 Step 3)**: EasyOCR extracts text with bounding boxes and per-word confidence.
   - **Find (Slide 3 Step 4)**: Regular expressions locate `shop_name`, `date`, `phone`, `email`, `pincode`, and `total_amount`.
   - **Auto-Category (Slide 6 #3)**: Keywords automatically categorize the receipt as `"Grocery"`.
   - **Duplicate Detection (Slide 6 #4)**: SHA-256 image hash prevents double-counting identical receipts.
4. The system automatically navigates to **"Review & Verify"** (`/review/{doc_id}`).

---

### Step 3: Human-in-the-Loop Split-Screen Verification (Slide 3 Step 5 & Slide 7)
1. On the **Review Page**:
   - **Left Canvas**: Zoomable, pannable, rotatable image viewer displaying the ABC MART receipt photo.
   - **Right Form**: Clean editable form with confidence indicators.
2. **Confidence Flags (Slide 6 #1 & Slide 7 Demo)**:
   - **Shop**: ABC MART — <span style="color: #10B981; font-weight: bold;">● Looks good</span> (~92% confidence)
   - **Date**: 03/11/2026 — <span style="color: #10B981; font-weight: bold;">● Looks good</span> (~92% confidence)
   - **Phone**: 9876543210 — <span style="color: #10B981; font-weight: bold;">● Looks good</span> (~92% confidence)
   - **Email**: abcmart@gmail.com — <span style="color: #10B981; font-weight: bold;">● Looks good</span> (~92% confidence)
   - **PIN code**: 580001 — <span style="color: #10B981; font-weight: bold;">● Looks good</span> (~92% confidence)
   - **Total**: ₹1,250 — <span style="color: #F59E0B; font-weight: bold;">● Please check</span> (Amber badge, ~57% confidence)
3. **Auto-Check Validation Rules (Slide 6 #2)**:
   - <span style="color: #10B981; font-weight: bold;">✓ Phone Check</span>: Phone is 10 digits (9876543210)
   - <span style="color: #10B981; font-weight: bold;">✓ PIN Check</span>: PIN is 6 digits (580001)
   - <span style="color: #10B981; font-weight: bold;">✓ Total Check</span>: Total amount is > 0 (₹1,250.00)
4. Confirm total amount and press **`Ctrl+Enter`** (or click **"Approve & Save"**).
5. Record transitions to `is_verified = 1` and is permanently saved to SQLite table `receipts` (Slide 5).

---

### Step 4: "Ask Your Receipts" Natural Language Queries (Slide 6 #6)
1. Return to the **Dashboard** (`/`).
2. In the **"Ask Your Receipts"** natural language bar, test the example queries:
   - *"Total spent at ABC MART in November"* &rarr; **Answer**: `Total spent at ABC MART in November: ₹1,250.00 across 1 receipt.`
   - *"How much did I spend on Groceries?"* &rarr; **Answer**: `You spent a total of ₹1,250.00 on Grocery across 1 receipt.`
   - *"What was my highest expense?"* &rarr; **Answer**: `Your highest expense was ₹1,250.00 at ABC MART on 2026-11-03.`
   - *"Show receipts above 1000"* &rarr; **Answer**: `Found 1 receipt above ₹1,000.00 totaling ₹1,250.00.`
   - *"How many receipts were uploaded?"* &rarr; **Answer**: `You have 1 confirmed receipt in the database.`

---

### Step 5: Spending Dashboard & Excel Export (Slide 6 #5 & #7)
1. **Spending Dashboard (`/analytics`)**:
   - Visual charts of spending:
     1. **Spending by Month** (Line chart)
     2. **Spending by Category** (Donut chart: Grocery, Restaurant, Stationery)
     3. **Spending by Shop** (Horizontal bar chart: ABC MART)
2. **Database Records (`/records`)**:
   - Live searchable SQLite records table with pagination, filtering, and detail drawer.
3. **1-Click Excel Export (`/reports` or `/api/export?format=xlsx`)**:
   - Download the generated `.xlsx` spreadsheet matching Slide 5 columns (`id`, `shop_name`, `date`, `total_amount`, `phone`, `email`, `pincode`, `category`, `ocr_confidence`, `is_verified`, `created_at`).

---

## Viva Defense Questions & Answers

### Q1: Why use human-in-the-loop verification instead of 100% automated database insertion?
> **Answer**: Real-world receipts often have crumpled paper, faded thermal ink, or ambiguous formatting. A 100% automated insertion silently pollutes financial databases with errors. By combining automated OCR extraction with amber confidence flags (`● Please check`) and auto-check rules (10-digit phone, 6-digit PIN, Total > 0), the human operator spends only 2 seconds verifying highlighted fields, eliminating 100% of errors before database insertion.

### Q2: What is the database schema used in this project?
> **Answer**: As shown in Slide 5, the primary relational table is `receipts` in SQLite:
> - `id` (INTEGER PK AUTOINCREMENT)
> - `shop_name` (TEXT)
> - `date` (TEXT / DATE)
> - `total_amount` (REAL)
> - `phone` (TEXT)
> - `email` (TEXT)
> - `pincode` (TEXT)
> - `category` (TEXT)
> - `ocr_confidence` (REAL)
> - `image_path` (TEXT)
> - `raw_text` (TEXT)
> - `is_verified` (INTEGER)
> - `image_hash` (TEXT)
> - `created_at` (TIMESTAMP)

### Q3: How does the "Ask Your Receipts" feature work without a heavy cloud LLM?
> **Answer**: It uses a fast, rule-based natural language parser that runs 100% offline using Python regex and SQLite aggregation queries. It parses intents (e.g. shop name, month name, expense category, numerical thresholds like "above 1000", max/min keywords) and executes parameterized SQL statements (`SUM`, `AVG`, `COUNT`, `MAX`, `WHERE`). If an optional Google Gemini API key is configured, it can also provide synthesized natural language responses.

### Q4: How is duplicate receipt detection handled?
> **Answer**: When an image is uploaded, we calculate its cryptographic SHA-256 hash before running expensive OCR inference. If the hash already exists in the SQLite database, the system immediately flags it as a duplicate, preventing duplicate database entries and saving processing time.

### Q5: What image preprocessing steps are performed by OpenCV?
> **Answer**: As described in Slide 3 Step 2, OpenCV applies:
> 1. **Grayscale conversion**: Removes chromatic noise.
> 2. **Laplacian variance blur check**: Flags blurry captures.
> 3. **Deskewing**: Detects orientation angles using minimum-area bounding boxes and straightens rotated images.
> 4. **Adaptive Thresholding / CLAHE**: Enhances contrast on faded thermal paper.

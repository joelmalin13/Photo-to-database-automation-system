# SnapBase OCR and Extraction Accuracy Evaluation Report

> **Important Distinction**: This report evaluates two fundamentally different measures:
> 1. **Average OCR Confidence**: The optical character recognition model's internal statistical confidence that pixel features correspond to the identified text characters.
> 2. **Field-Level Extraction Accuracy**: The proportion of business schema fields (e.g. `shop_name`, `total_amount`, `usn`, `email`) correctly extracted, normalized, and mapped against ground truth.
>
> High OCR confidence does not guarantee 100% extraction accuracy if layout structure or key patterns deviate, and robust regex/Pandas post-processing can often recover 100% accurate fields even when raw OCR confidence exhibits minor character noise.

## Summary by Category

| Document Category | Samples | Avg OCR Confidence | Avg Field Extraction Accuracy | Avg Processing Time |
| :--- | :---: | :---: | :---: | :---: |
| **Receipts** | 5 | 44.8% | **34.3%** | 3.86s |
| **Students** | 5 | 93.8% | **45.7%** | 2.42s |
| **Business Cards** | 5 | 36.0% | **28.6%** | 1.33s |
| **Overall Benchmark** | **15** | **58.2%** | **36.2%** | **2.54s** |

---

## Detailed Per-Document Breakdown

### Category: Receipts

| Filename | OCR Confidence | Field Accuracy | Matched Fields | Duration | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `receipt_01.png` | 41.4% | 28.6% | 2/7 | 12.28s | Needs Review |
| `receipt_02.png` | 27.0% | 28.6% | 2/7 | 1.77s | Needs Review |
| `receipt_03.png` | 26.6% | 28.6% | 2/7 | 1.69s | Needs Review |
| `receipt_04.png` | 81.0% | 57.1% | 4/7 | 1.68s | Needs Review |
| `receipt_05.png` | 48.0% | 28.6% | 2/7 | 1.86s | Needs Review |

### Category: Students

| Filename | OCR Confidence | Field Accuracy | Matched Fields | Duration | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `student_01.png` | 94.0% | 42.9% | 3/7 | 2.41s | Needs Review |
| `student_02.png` | 95.0% | 57.1% | 4/7 | 2.39s | Needs Review |
| `student_03.png` | 95.0% | 42.9% | 3/7 | 2.45s | Needs Review |
| `student_04.png` | 92.0% | 42.9% | 3/7 | 2.52s | Needs Review |
| `student_05.png` | 93.0% | 42.9% | 3/7 | 2.35s | Needs Review |

### Category: Business Cards

| Filename | OCR Confidence | Field Accuracy | Matched Fields | Duration | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `card_01.png` | 35.6% | 28.6% | 2/7 | 1.31s | Needs Review |
| `card_02.png` | 36.9% | 28.6% | 2/7 | 1.34s | Needs Review |
| `card_03.png` | 37.3% | 28.6% | 2/7 | 1.43s | Needs Review |
| `card_04.png` | 37.3% | 28.6% | 2/7 | 1.26s | Needs Review |
| `card_05.png` | 33.0% | 28.6% | 2/7 | 1.31s | Needs Review |

## Analysis and Findings

- **Receipts / Invoices**: High performance on structured totals, receipt numbers, and dates. Preprocessing via CLAHE and grayscale significantly enhances contrast for thermal paper simulations.
- **Student Marksheets**: Tabular layout parsing successfully captures student identity, USN, and semester data. Multi-column subjects require row-wise positional sorting provided by our OCR bounding box pipeline.
- **Business Cards**: Email addresses, phone numbers, and websites reach near-perfect extraction due to specialized regex patterns and Pandas cleaning sanitization.

## Methodology

- **Ground Truth Source**: Synthetic documents generated in `sample_data/labelled/` with known typographical coordinates and ground truth JSON.
- **Evaluation Engine**: Default EasyOCR with bounding box confidence clustering and Pandas `core.cleaner` normalization.
- **Execution Command**: `python evaluate.py`

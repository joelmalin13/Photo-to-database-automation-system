# PIXELMIND: AI-Powered Visual Intelligence Database

> *"Every Image Has Data. Make It Searchable."*

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![YOLOv8n](https://img.shields.io/badge/YOLOv8n-Ultralytics-orange.svg)](https://docs.ultralytics.com/)
[![OpenCLIP](https://img.shields.io/badge/OpenCLIP-ViT--B--32-purple.svg)](https://github.com/mlfoundations/open_clip)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-red.svg)](https://www.sqlalchemy.org/)
[![Database](https://img.shields.io/badge/MySQL%20%7C%20SQLite%20Fallback-active-brightgreen.svg)](https://www.mysql.com/)

**PixelMind** is an enterprise-grade visual intelligence platform that ingests unstructured photographs, detects objects, understands scene composition, extracts an authoritative "Image DNA" visual fingerprint, stores everything as structured database records, and renders it instantly searchable via natural language sentences, visual similarity, and interactive conversational queries.

---

## Architecture Overview

```mermaid
flowchart TD
    Client["Browser / HTMX + Alpine.js + Tailwind"] -->|HTTP / REST| API["FastAPI Application (app.main)"]
    API --> ServiceLayer["Service Layer (app/services)"]
    
    subgraph ServiceLayer ["Service Layer"]
        ImageSvc["ImageService"]
        SearchSvc["SearchService"]
        DnaSvc["DnaService"]
        AnalyticsSvc["AnalyticsService"]
    end
    
    subgraph AI_Engines ["Computer Vision & AI Engines"]
        YOLO["YOLOv8n Detector (Object Detection)"]
        CLIP["OpenCLIP ViT-B-32 (512-dim Latent Vectors)"]
        KMeans["OpenCV K-Means (Dominant Color Palette)"]
        PerceptualHash["dHash 64-bit + SHA-256 Hashes"]
        QueryParser["Rule-Based Parameterized Query Parser"]
    end

    ImageSvc --> YOLO
    ImageSvc --> CLIP
    ImageSvc --> KMeans
    ImageSvc --> PerceptualHash
    SearchSvc --> CLIP
    SearchSvc --> QueryParser
    DnaSvc --> CLIP

    ServiceLayer --> CRUD["db.crud (Parameterized Queries)"]
    CRUD --> EngineRouter{"Resilient Engine"}
    EngineRouter -->|Default| MySQL[("MySQL 8.0+ Database (pixelmind)")]
    EngineRouter -->|Fallback| SQLite[("Local SQLite Database (data/pixelmind.db)")]
```

---

## Core Capabilities

### 1. Object Detection (YOLOv8n)
- Rapid CPU-optimized real-time detection across 80 COCO classes.
- Stores detected label, count, bounding boxes `[x1, y1, x2, y2]`, and confidence scores.
- Automatically saves annotated images with custom colored bounding boxes and labels into `/data/annotated`.

### 2. Automatic Categorization
- Maps detected labels to 9 canonical categories via `config/categories.json`:
  - `Nature`, `Animals`, `Vehicles`, `Technology`, `Food`, `Architecture`, `Human activities`, `Sports`, `Electronics`
- Resolves image-level category through object distribution weighting, with zero-shot OpenCLIP as an automated tie-breaker when detections are ambiguous or absent.

### 3. Image DNA Visual Fingerprint
- **Dominant Colors**: Extracts top 5 dominant colors with HEX, RGB, and pixel area percentages using OpenCV K-Means clustering.
- **Hashes**: Cryptographic SHA-256 for instant duplicate blocking, plus 64-bit perceptual difference hash (`dHash`) for visual similarity.
- **Composition Summary**: Aspect ratio, orientation (landscape/portrait/square), object density, and category breakdown.
- **Vector Embedding**: 512-dimensional normalized OpenCLIP `ViT-B-32` latent embedding blob.

### 4. Natural Language Image Search
- Natural language query input (e.g. *"a red car parked beside a tree"*).
- Combines OpenCLIP text-to-image cosine similarity with detected object label matches for high-precision ranking.
- Real-time debounced live search powered by HTMX.

### 5. Ask Your Images (Rule-Based Visual Q&A)
Converts natural language questions into safe, parameterized SQL queries without requiring an external LLM:
- *"How many cars have been detected across all images?"*
- *"Find images containing dogs"*
- *"Show images containing both people and motorcycles"*
- *"Which image contains the maximum number of objects?"*
- *"Show all outdoor images containing at least two vehicles and one person"*
- *"Find all images containing electronic devices"*

### 6. Visual Analytics Dashboard
- Key Performance Indicators (Total Images, Detected Objects, Storage Volume, Anomaly Flags).
- Protected empty states (`"No data yet"`) when database has zero records.
- Five Chart.js visualizations:
  1. Category Distribution (Doughnut)
  2. Top Detected Objects (Bar)
  3. Scene Classification (Horizontal Bar)
  4. Environment Breakdown: Indoor vs. Outdoor (Polar/Pie)
  5. Monthly Ingestion Velocity (Smooth Line)

### 7. Reverse Visual Search & Anomaly Detection
- Reverse image search supporting 4 comparison modes:
  - **Overall**: CLIP latent cosine similarity
  - **Object**: Generalized Jaccard index over labels and counts
  - **Color**: Weighted Euclidean RGB palette distance
  - **Scene**: Scene label and environment agreement
- Automated statistical anomaly flagging identifying unusual object counts or incongruous category pairings.

---

## Design System

- **Clean SaaS Aesthetics**: Crisp pure white background (`#FFFFFF`), near-black text (`#1F1F1F`), neutral gray borders (`#E5E5E5`).
- **Signature Gradient Banner**: Subtle top header gradient transitioning from deep charcoal (`#111111`) to primary red (`#C62828`).
- **Zero Emojis**: Crisp SVG icons powered by Lucide throughout all templates and buttons.
- **Responsive Layout**: Fixed collapsible sidebar on desktop, responsive slide-out navigation on mobile devices.

---

## Installation & Setup

### Prerequisites
- Python 3.11+
- Git

### 1. Clone & Set Up Environment
```bash
git clone <repo-url>
cd "Photo to database automation system"

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```env
# Database URL (Defaults to MySQL, automatically falls back to SQLite if unreachable)
DATABASE_URL=mysql+mysqlconnector://root:password@localhost:3306/pixelmind

# Confidence & Thresholds
CONFIDENCE_THRESHOLD=0.25
MAX_FILE_SIZE_MB=15

# Optional: Google Gemini API Key (only used if external LLM fallback is requested)
GEMINI_API_KEY=
```

### 3. Generate & Ingest Sample Images
```bash
# Generate 12 varied test images across canonical categories
python sample_data/generate_sample_images.py

# Ingest sample images into the database
python sample_data/ingest_samples.py
```

### 4. Run the Application
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Open your browser and navigate to:
- **Web Application**: [http://localhost:8000](http://localhost:8000)
- **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## Running Automated Tests

Run the complete test suite with verbose output:
```bash
python -m pytest tests/ -v
```

The test suite covers:
- `tests/test_categorizer.py`: Canonical label mapping, frequency determination, and fallback rules.
- `tests/test_dna.py`: SHA-256 duplicate hashing, perceptual dHash distance, K-Means dominant color extraction, and composition statistics.
- `tests/test_query_parser.py`: All 6 required natural language benchmark queries and unrecognized fallback suggestions.
- `tests/test_similarity.py`: Object Jaccard, Color Euclidean, Scene alignment, and CLIP latent cosine similarity.
- `tests/test_crud.py`: Relational persistence, duplicate hash lookups, cascading deletions, and analytics summaries.
- `tests/test_api.py`: All 8 HTML page views, upload endpoint, search endpoint, Q&A endpoint, and database health status.

---

## REST API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/images` | Upload and ingest one or multiple image files (multipart/form-data) |
| `GET` | `/api/images` | Search, filter by category/env/label, sort, and paginate stored images |
| `GET` | `/api/images/{id}` | Retrieve comprehensive image metadata, bounding boxes, and DNA |
| `DELETE`| `/api/images/{id}` | Delete image and cascade-delete child detections, DNA, and anomaly records |
| `POST` | `/api/search` | Semantic text-to-image search using natural language query |
| `POST` | `/api/ask` | Natural language question answering about the image database |
| `POST` | `/api/similar` | Reverse visual search matching an uploaded query image |
| `GET` | `/api/analytics` | Aggregated metrics and distributions for Chart.js |
| `GET` | `/api/status` | Runtime database connectivity and active model telemetry |

---

## Project Structure

```
Photo to database automation system/
│
├── app/
│   ├── main.py                     # FastAPI application setup, lifecycle, and route mounts
│   ├── dependencies.py             # Database session dependency injection
│   ├── routers/
│   │   ├── pages.py                # Server-rendered HTML routes and HTMX partials
│   │   └── api.py                  # OpenAPI REST endpoints
│   ├── services/
│   │   ├── image_service.py        # End-to-end ingestion pipeline orchestrator
│   │   ├── search_service.py       # Semantic text search and visual Q&A
│   │   ├── dna_service.py          # Reverse visual similarity search
│   │   └── analytics_service.py    # Metric aggregation for Chart.js
│   ├── static/
│   │   ├── css/app.css             # Custom utility styling and scrollbar rules
│   │   └── js/app.js               # Alpine.js helpers and toast utilities
│   └── templates/                  # Jinja2 HTML templates
│       ├── base.html               # Sidebar layout, top banner, and navigation
│       ├── dashboard.html          # KPI stat cards and visual analytics
│       ├── upload.html             # Multi-file drag & drop portal
│       ├── gallery.html            # Image grid with filter bar and pagination
│       ├── image_detail.html       # Split view: original vs annotated, DNA card
│       ├── search.html             # Natural language semantic search
│       ├── ask.html                # "Ask Your Images" interactive terminal
│       ├── similar.html            # Reverse visual similarity portal
│       ├── analytics.html          # Deep Chart.js visual analytics
│       ├── settings.html           # System diagnostics and connection telemetry
│       └── partials/               # HTMX partial fragments
│
├── core/                           # Computer Vision & Intelligence Core
│   ├── anomaly.py                  # Statistical outlier detection
│   ├── categorizer.py              # Automatic category mapping & tie-breaker
│   ├── detector_base.py            # Base detector abstract class & factory
│   ├── dna.py                      # K-Means dominant colors, dHash, composition
│   ├── embedder.py                 # OpenCLIP ViT-B-32 singleton vector embedder
│   ├── exceptions.py               # Custom domain exception hierarchy
│   ├── query_parser.py             # Rule-based natural language SQL query parser
│   ├── scene.py                    # Scene and indoor/outdoor classifier
│   ├── similarity.py               # 4-mode reverse similarity calculators
│   └── yolo_detector.py            # YOLOv8n object detection and box renderer
│
├── database/
│   └── schema.sql                  # MySQL 8.0+ DDL schema definition
│
├── db/
│   ├── models.py                   # SQLAlchemy 2.0 ORM data models
│   ├── session.py                  # Resilient database connection with SQLite fallback
│   └── crud.py                     # Parameterized SQL queries and aggregations
│
├── config/
│   ├── settings.py                 # Pydantic configuration & environment settings
│   ├── categories.json             # 80 COCO to 9 canonical categories mapping
│   └── scenes.json                 # Scene types and environment definitions
│
├── sample_data/
│   ├── generate_sample_images.py   # Synthetic test image generator
│   └── ingest_samples.py           # Database pre-population script
│
├── tests/                          # Automated Pytest suite (32 tests, 100% passing)
│   ├── test_api.py
│   ├── test_categorizer.py
│   ├── test_crud.py
│   ├── test_dna.py
│   ├── test_query_parser.py
│   └── test_similarity.py
│
├── requirements.txt                # Production dependencies
└── README.md                       # System documentation
```

---

## Limitations & Future Enhancements

1. **Vector Index Acceleration**:
   - Current similarity calculations run sub-100ms on CPU using NumPy vectorized cosine operations. For datasets exceeding 100,000 images, integrating an approximate nearest neighbor (ANN) index such as FAISS or pgvector/Milvus will preserve sub-10ms latency.
2. **Video Stream Ingestion**:
   - The current architecture processes static photographs. Extending the ingestion service to sample video keyframes using OpenCV would enable automated video visual intelligence indexing.
3. **Multi-Model Ensembles**:
   - Adding specialized face detection (RetinaFace) or OCR alongside object detection for composite multimodal documents.

---

## License

This project is licensed under the MIT License.

# PIXELMIND: AI-Powered Visual Intelligence Database

> *"Every Image Has Data. Make It Searchable."*

[![Vercel Deployment](https://img.shields.io/badge/Vercel-Serverless%20Ready-black.svg?logo=vercel)](https://vercel.com/)
[![Python 3.12](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Google Gemini](https://img.shields.io/badge/Gemini%202.5%20Flash-Vision%20%26%20Embeddings-4285F4.svg?logo=google)](https://aistudio.google.com/)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL%20%26%20Storage-3ECF8E.svg?logo=supabase)](https://supabase.com/)
[![Bundle Size](https://img.shields.io/badge/Serverless%20Bundle-167%20MB%20(%3C%20400%20MB)-brightgreen.svg)]()

---

## Live Demo & Public Link

- **Production Vercel URL:** `https://your-pixelmind-app.vercel.app` *(Deploy below)*
- **Live Tunnel (Temporary):** `https://basket-significantly-acknowledged-outcomes.trycloudflare.com`
- **Health Telemetry:** `GET /health`

---

## Overview

**PixelMind** is an enterprise visual intelligence platform that ingests unstructured photographs, automatically detects objects, classifies scene environments, computes an authoritative **Image DNA** visual fingerprint, persists structured records across hosted relational databases, and renders them instantly searchable via **natural language sentences**, **semantic reverse visual similarity**, and **interactive conversational queries**.

Designed from the ground up with **Dual-Mode AI Architecture**, PixelMind operates seamlessly in two environments:
1. **Cloud Serverless Mode (Vercel)**: Zero heavy deep-learning bundle (< 170 MB uncompressed, strictly under Vercel's 500 MB ceiling). Uses **Google Gemini 2.5 Flash** for single-call structured vision and **text-embedding-004**, **Supabase Storage** for assets, and **Supabase / Neon PostgreSQL** (or MySQL) via SQLAlchemy `NullPool`.
2. **Local Workstation Mode**: Offline CPU-friendly **YOLOv8n** (Ultralytics) + **OpenCLIP ViT-B-32**, pure Pillow / NumPy color clustering, and local filesystem / SQLite / MySQL storage.

---

## Dual-Mode System Architecture

```mermaid
flowchart TD
    subgraph Client ["Client Browser (Tailwind + Alpine.js + HTMX)"]
        UI["Upload / Search / Gallery / DNA"]
        Canvas["Offscreen Canvas Resizer (Max 1600px, JPEG 0.85)"]
        UI --> Canvas
    end

    Canvas -->|Payload < 800 KB| Router{"Vercel / Local Host"}

    subgraph Serverless ["FastAPI Serverless Application (index.py)"]
        App["FastAPI Entrypoint (app.main)"]
        StorageFactory["Storage Factory (LocalStorage vs SupabaseStorage)"]
        DetectorFactory["Detector Factory (LocalDetector vs CloudDetector)"]
        EmbedderFactory["Embedder Factory (LocalEmbedder vs CloudEmbedder)"]
        DBPool["SQLAlchemy 2.0 (NullPool Serverless-Safe)"]
    end

    Router --> App
    App --> StorageFactory
    App --> DetectorFactory
    App --> EmbedderFactory
    App --> DBPool

    subgraph CloudStack ["Cloud Mode (AI_MODE=cloud)"]
        Gemini["Google Gemini 2.5 Flash (Vision + JSON Schema)"]
        GeminiEmbed["Gemini text-embedding-004 (768-dim Embeddings)"]
        SupaStore[("Supabase Storage REST API")]
        SupaDB[("Supabase / Neon PostgreSQL (psycopg)")]
    end

    subgraph LocalStack ["Local Mode (AI_MODE=local)"]
        YOLO["YOLOv8n (80 COCO Classes, CPU)"]
        CLIP["OpenCLIP ViT-B-32 (512-dim Latent Vectors)"]
        LocalDisk[("Local Filesystem (uploads/ / data/)")]
        LocalDB[("MySQL 8.0+ / SQLite Fallback")]
    end

    DetectorFactory -->|Cloud| Gemini
    DetectorFactory -->|Local| YOLO
    EmbedderFactory -->|Cloud| GeminiEmbed
    EmbedderFactory -->|Local| CLIP
    StorageFactory -->|Cloud| SupaStore
    StorageFactory -->|Local| LocalDisk
    DBPool -->|Cloud| SupaDB
    DBPool -->|Local| LocalDB
```

---

## Deploying on Vercel (Step-by-Step)

Deploying PixelMind to Vercel takes approximately 5 minutes.

### Step 1: Provision Supabase (Database & Storage)

1. Navigate to [Supabase](https://supabase.com/) and create a new project.
2. Under **Project Settings &rarr; Database &rarr; Connection String &rarr; URI**:
   - Copy the PostgreSQL URI.
   - Replace the driver prefix with `postgresql+psycopg://` (e.g. `postgresql+psycopg://postgres.YOUR_PROJECT_ID:YOUR_PASSWORD@aws-0-us-east-1.pooler.supabase.com:6543/postgres`).
3. Under **Storage**:
   - Click **New Bucket**.
   - Name it `photos` (or any custom name).
   - Toggle **Public bucket** ON so uploaded and annotated images can be viewed publicly.
4. Under **Project Settings &rarr; API**:
   - Copy your **Project URL** (`https://xyzcompany.supabase.co`).
   - Copy your **service_role secret key** (needed for authorized serverless image uploads).

### Step 2: Get a Free Google Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/).
2. Click **Create API Key**.
3. Copy the generated key (`AIza...`).

### Step 3: Deploy to Vercel

1. Push this repository to GitHub or GitLab.
2. In the [Vercel Dashboard](https://vercel.com/new), click **Import Project** and select this repository.
3. Keep default settings:
   - **Framework Preset**: `Other`
   - **Root Directory**: `./`
4. Expand **Environment Variables** and configure the following:

| Variable Name | Required | Example / Description |
|:---|:---:|:---|
| `AI_MODE` | **Yes** | `cloud` (forces zero-torch Google Gemini inference) |
| `DB_URL` | **Yes** | `postgresql+psycopg://postgres:pass@host:5432/postgres` |
| `GEMINI_API_KEY` | **Yes** | `AIzaSy...` (Google Gemini API key) |
| `GEMINI_MODEL` | No | `gemini-2.5-flash` (default) |
| `GEMINI_EMBED_MODEL` | No | `text-embedding-004` (default) |
| `STORAGE_BACKEND` | **Yes** | `supabase` |
| `SUPABASE_URL` | **Yes** | `https://your-id.supabase.co` |
| `SUPABASE_SERVICE_KEY` | **Yes** | Your Supabase service role secret key |
| `SUPABASE_BUCKET` | **Yes** | `photos` |

5. Click **Deploy**. Vercel will install the lightweight dependencies from `requirements.txt` (~167 MB uncompressed) and deploy the ASGI FastAPI application via `index.py`.

### Step 4: Verify Deployment Health

Open your deployed URL in your browser or run:
```bash
curl https://your-pixelmind-app.vercel.app/health
```

Expected JSON response:
```json
{
  "status": "healthy",
  "mode": "cloud",
  "is_vercel": true,
  "database": {
    "engine_name": "PostgreSQL",
    "connected": true,
    "message": "Connected to remote database."
  },
  "storage": {
    "backend": "supabase",
    "status": "ready"
  },
  "ai": {
    "detector": "gemini-2.5-flash",
    "embedder": "text-embedding-004",
    "gemini_configured": true,
    "supabase_configured": true
  }
}
```

---

## Vercel Constraints & Architectural Solutions

| Vercel Hard Constraint | Impact | PixelMind Engineering Solution |
|:---|:---|:---|
| **500 MB Uncompressed Bundle Limit** | `torch`, `ultralytics`, `open-clip-torch`, `opencv-python`, and `scipy` together exceed 2.5 GB. | Replaced heavy C++/PyTorch libraries in cloud mode with `google-genai` (< 12 MB) and pure Pillow / NumPy algorithms. Production bundle is **167.4 MB**. |
| **4.5 MB Request / Response Limit** | High-resolution phone photos (8–20 MB) would fail with `413 Payload Too Large`. | Implemented offscreen browser HTML `<canvas>` downscaling (max 1600px longest dimension, JPEG 0.85 re-encoding) in `upload.html`. Typical upload size: 200–800 KB. |
| **Read-Only & Ephemeral Filesystem** | Local SQLite `.db` and `/uploads` folders are lost upon function termination or read-only. | In cloud mode, all binary files stream directly to **Supabase Storage** and metadata is saved to **Supabase PostgreSQL**. Temporary files strictly use `/tmp`. |
| **Serverless Execution Lifespan** | BackgroundTasks and daemon threads terminate when the response is returned. | Process each image inside its own HTTP request (`POST /api/images/single`) sequentially with browser-side queueing. |
| **Database Connection Exhaustion** | Serverless function concurrency can quickly exceed database max connection limits. | Configured SQLAlchemy 2.0 with `NullPool` in serverless mode to open and close connections cleanly per invocation. |

---

## Local Development & Offline Mode

To run PixelMind locally on your workstation using local CPU deep learning models:

```bash
# 1. Clone repository
git clone https://github.com/your-username/pixelmind.git
cd pixelmind

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install production and local deep-learning dependencies
pip install -r requirements.txt
pip install -r requirements-local.txt

# 4. Configure local environment
cp .env.example .env
# Edit .env: Set AI_MODE=local, DB_URL=sqlite:///data/pixelmind.db

# 5. Start development server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Visit `http://127.0.0.1:8000` in your web browser.

---

## REST API Reference

| Method | Endpoint | Description |
|:---|:---|:---|
| `GET` | `/health` | Runtime system telemetry, AI mode, DB connection health, and storage backend status (no secrets). |
| `POST` | `/api/images/single` | Sequential single-image upload with browser canvas compression compatibility. |
| `POST` | `/api/images` | Multi-image batch ingestion endpoint. |
| `GET` | `/api/images` | Filter, search, and paginate stored images by label, category, environment, and date. |
| `GET` | `/api/images/{id}` | Detailed image record with bounding boxes, dominant colors, and Image DNA. |
| `POST` | `/api/images/{id}/retry` | Re-analyze a failed image with the active AI detector without re-uploading. |
| `DELETE` | `/api/images/{id}` | Cascade-delete an image and its detections, DNA, and anomaly records. |
| `POST` | `/api/search` | Natural language image search (e.g. `{"query": "a red car parked by a tree"}`). |
| `POST` | `/api/ask` | "Ask Your Images" rule-based visual intelligence Q&A. |
| `POST` | `/api/similar` | Reverse image similarity search across 4 modes (`overall`, `object`, `color`, `scene`). |
| `GET` | `/api/analytics` | Aggregated visual metrics and KPI data for Chart.js dashboards. |

---

## Automated Verification & Test Suite

Verify all 36 test cases and measure serverless bundle compliance:

```bash
# Run complete test suite (includes cloud mode zero-torch module isolation tests)
python -m pytest tests/ -v

# Run bundle size verification against Vercel 500 MB ceiling
python scripts/check_bundle_size.py
```

### Bundle Size Audit Output:
```
============================================================
PIXELMIND VERCEL BUNDLE SIZE AUDIT
============================================================
PASS: No heavy deep-learning packages (torch, ultralytics, cv2) found.
Package                        | Estimated Size 
--------------------------------------------------
fastapi                        |     1.59 MB
uvicorn                        |     0.70 MB
jinja2                         |     1.12 MB
python-multipart               |     0.18 MB
httpx                          |     0.71 MB
python-dotenv                  |     0.21 MB
python-dateutil                |     0.71 MB
sqlalchemy                     |    18.39 MB
psycopg                        |     1.71 MB
pymysql                        |     0.32 MB
mysql-connector-python         |    59.39 MB
pydantic                       |     3.62 MB
pydantic-settings              |     0.60 MB
numpy                          |    51.20 MB
pillow                         |    15.41 MB
google-genai                   |    11.54 MB
--------------------------------------------------
Total Measured Bundle          |   167.40 MB

Audit Result:
  Measured Size : 167.40 MB
  Target Budget : 400.0 MB
  Vercel Ceiling: 500.0 MB

SUCCESS: Bundle size (167.40 MB) is well within Vercel's serverless limits!
```

---

## License

MIT License. Built with FastAPI, Tailwind CSS, Alpine.js, and Google Gemini.

# UniMat AI

**AI-Driven Standardization and Harmonization of Material Master Codes for Central Public Sector Enterprises (CPSEs)**

---

## How to Start the Application

### 1. Start the Backend (FastAPI)
Open a terminal and navigate to the `backend` folder, activate the virtual environment, and run the server.

```bash
cd backend
venv\Scripts\activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Start the Frontend (Next.js)
Open a *new* terminal and navigate to the `frontend` folder, then run the development server.

```bash
cd frontend
npm run dev
```

Once both servers are running, open [http://localhost:3000](http://localhost:3000) in your web browser.

---

## GPU Acceleration (Optional — Recommended for Large Datasets)

The embedding model (`BAAI/bge-base-en-v1.5`) runs on CPU by default. To enable **GPU acceleration** with CUDA, follow these steps:

### Prerequisites
- NVIDIA GPU with CUDA support
- [CUDA Toolkit](https://developer.nvidia.com/cuda-downloads) installed (11.8+ recommended)
- [cuDNN](https://developer.nvidia.com/cudnn) installed

### Step 1: Install PyTorch with CUDA Support
Uninstall the CPU-only version and install the CUDA-enabled build:

```bash
cd backend
venv\Scripts\activate

# Uninstall CPU-only torch
pip uninstall torch torchvision torchaudio -y

# Install CUDA 11.8 build (adjust cu118 to your CUDA version)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# For CUDA 12.1:
# pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Step 2: Verify GPU is Detected

```bash
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}'); print(f'Device: {torch.cuda.get_device_name(0)}') if torch.cuda.is_available() else None"
```

Expected output:
```
CUDA available: True
Device: NVIDIA GeForce RTX 3060   (or your GPU name)
```

### Step 3: Run as Normal
No code changes needed — the `sentence-transformers` library and Qdrant's FastEmbed automatically detect and use the GPU when CUDA-enabled PyTorch is installed.

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> **Note:** GPU acceleration primarily speeds up the **embedding generation** step of the pipeline. For datasets under 500 items, the difference is marginal. For 5,000+ items, expect **3-5x speedup**.

---

## Architecture Overview

| Component | Technology |
|---|---|
| **Frontend** | Next.js 14 (React + TypeScript) |
| **Backend** | FastAPI (Python 3.11) |
| **Database** | PostgreSQL |
| **Vector DB** | Qdrant (local, file-backed) |
| **Embeddings** | BAAI/bge-base-en-v1.5 (384-dim dense) |
| **LLM** | Google Gemini 2.5 Flash |
| **NLP** | spaCy + custom abbreviation expansion |

## Pipeline

1. **NLP Standardization** — spaCy tokenization, abbreviation expansion, unit normalization
2. **Vector Embedding** — BGE dense embeddings indexed in Qdrant
3. **Tri-State Classification** — Duplicate (≥82%) / Near-Duplicate (75-82%) / Unique (<75%)
4. **LLM Code Generation** — Gemini generates standardized CNMC names for unique clusters
5. **Human-in-the-Loop Review** — Cluster-based review center for near-duplicate resolution

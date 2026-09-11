"""
UniMat AI — FastAPI Application Entry Point

Production-grade API server for the Unified Material Master Framework.
SIH 2026 Problem Statement 26099.
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.config import get_settings
from app.database import Base, engine, get_db
from app.schemas import HealthResponse

# Import all models so they are registered with the Base
from app.models import (  # noqa: F401
    CPSEProfile, UploadSession, NationalCode, MaterialItem,
    LegacyMapping, AuditTrail, PipelineRun,
)

# Import routers
from app.routers import upload, pipeline, materials, review, dashboard

# ─── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("unimat")

settings = get_settings()


# ─── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    # ── Startup ─────────────────────────────────────────────────────────────────
    logger.info("🏭 UniMat AI Backend starting up...")

    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables created/verified")

    # Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    logger.info(f"📁 Upload directory: {os.path.abspath(settings.UPLOAD_DIR)}")

    # Ensure Qdrant directory exists
    os.makedirs(settings.QDRANT_PATH, exist_ok=True)
    logger.info(f"🧠 Qdrant DB path: {os.path.abspath(settings.QDRANT_PATH)}")

    logger.info(f"🔑 Gemini API Key: {'configured' if settings.GEMINI_API_KEY else 'NOT SET'}")
    logger.info(f"📊 Embedding model: {settings.EMBEDDING_MODEL}")
    logger.info(f"🎯 Thresholds — Duplicate: >{settings.DUPLICATE_THRESHOLD}, "
                 f"Near-Dup: {settings.NEAR_DUPLICATE_THRESHOLD}-{settings.DUPLICATE_THRESHOLD}")
    logger.info("🚀 UniMat AI Backend ready!")

    yield

    # ── Shutdown ────────────────────────────────────────────────────────────────
    logger.info("🏭 UniMat AI Backend shutting down...")


# ─── FastAPI App ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="UniMat AI — Unified Material Master Framework",
    description=(
        "AI-Driven Standardization and Harmonization of Material Codes Across CPSEs. "
        "SIH 2026 Problem Statement 26099: 'One Nation — One Material Code'."
    ),
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS Middleware ────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",       # Next.js dev server
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Register Routers ──────────────────────────────────────────────────────────
app.include_router(upload.router)
app.include_router(pipeline.router)
app.include_router(materials.router)
app.include_router(review.router)
app.include_router(dashboard.router)

# ─── Admin Router (For Prototype Demos) ───────────────────────────────────────
admin_router = APIRouter(prefix="/api/admin", tags=["Admin"])

@admin_router.post("/reset-db")
def reset_database(db: Session = Depends(get_db)):
    """Reset the entire database (PostgreSQL + Qdrant) for a fresh prototype demo."""
    # First, truncate all PostgreSQL tables (cascade to handle foreign keys)
    db.execute(text("TRUNCATE TABLE pipeline_runs, audit_trail, legacy_mappings, material_items, national_codes, upload_sessions, cpse_profiles CASCADE;"))
    db.commit()
    
    # Reset Qdrant vector collection — delete and recreate
    try:
        from app.services import vector_service
        vector_service.reset_collection()
        logger.info("Qdrant collection reset successfully")
    except Exception as e:
        logger.error(f"Failed to reset Qdrant: {e}")

    return {"message": "Database successfully wiped (PostgreSQL + Qdrant)."}

app.include_router(admin_router)


# ─── Root & Health ──────────────────────────────────────────────────────────────
@app.get("/", tags=["Root"])
def root():
    """API root — redirects to docs."""
    return {
        "name": "UniMat AI",
        "version": "2.0.0",
        "description": "AI-Driven Material Code Harmonization API",
        "docs": "/docs",
    }


@app.get("/api/health", response_model=HealthResponse, tags=["Health"])
def health_check():
    """Health check endpoint."""
    db_status = "connected"
    vector_status = "ready"

    try:
        from sqlalchemy import text
        from app.database import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as e:
        db_status = f"error: {e}"

    return HealthResponse(
        status="healthy",
        version="2.0.0",
        database=db_status,
        vector_db=vector_status,
    )

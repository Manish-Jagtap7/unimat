"""
UniMat AI — Pipeline Router

Triggers and monitors the AI processing pipeline.
"""

import asyncio
from typing import List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
import logging
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import PipelineRun, UploadSession, PipelineStatus
from app.schemas import PipelineRunRequest, PipelineStatusResponse

logger = logging.getLogger("unimat")

router = APIRouter(prefix="/api/pipeline", tags=["Pipeline"])


@router.post("/run", response_model=List[PipelineStatusResponse])
async def run_pipeline(
    request: PipelineRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Trigger the AI pipeline for one or more upload sessions.
    
    The pipeline runs in the background:
    1. NLP Standardization (spaCy + Regex)
    2. Vector Embedding (ChromaDB + BGE)
    3. Tri-State Classification
    4. LLM Batch Code Generation (Gemini)
    """
    pipeline_runs = []

    # We collect all run_ids to process them sequentially in a single background task
    # to avoid race conditions with Qdrant vector insertions.
    run_ids = []
    
    for session_id in request.session_ids:
        # Validate session exists
        session = db.query(UploadSession).filter(UploadSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail=f"Upload session {session_id} not found")

        # Check if pipeline already running for this session
        existing = (
            db.query(PipelineRun)
            .filter(
                PipelineRun.upload_session_id == session_id,
                PipelineRun.status.in_([PipelineStatus.PENDING, PipelineStatus.RUNNING]),
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Pipeline already running for session {session_id} (run ID: {existing.id})",
            )

        # Create pipeline run record
        run = PipelineRun(
            upload_session_id=session_id,
            status=PipelineStatus.PENDING,
            total_items=session.row_count,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        
        run_ids.append(run.id)

        pipeline_runs.append(PipelineStatusResponse(
            id=run.id,
            upload_session_id=run.upload_session_id,
            status=run.status,
            current_step=run.current_step,
            progress_pct=run.progress_pct,
            total_items=run.total_items,
            duplicates_found=run.duplicates_found,
            near_duplicates_found=run.near_duplicates_found,
            unique_items=run.unique_items,
            error_message=run.error_message,
            started_at=run.started_at,
            completed_at=run.completed_at,
        ))

    # Resolve thresholds: use request values if provided, else config defaults
    settings = get_settings()
    dup_t = request.dup_threshold if request.dup_threshold is not None else settings.DUPLICATE_THRESHOLD
    near_t = request.near_dup_threshold if request.near_dup_threshold is not None else settings.NEAR_DUPLICATE_THRESHOLD

    # Schedule background processing
    if run_ids:
        background_tasks.add_task(
            _execute_pipeline_batch, 
            run_ids, 
            dup_t, 
            near_t
        )

    return pipeline_runs


@router.get("/status", response_model=PipelineStatusResponse)
def get_latest_pipeline_status(db: Session = Depends(get_db)):
    """Return the most recent pipeline run status (for frontend polling without run_id)."""
    run = (
        db.query(PipelineRun)
        .order_by(PipelineRun.started_at.desc())
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="No pipeline runs found")

    return PipelineStatusResponse(
        id=run.id,
        upload_session_id=run.upload_session_id,
        status=run.status,
        current_step=run.current_step,
        progress_pct=run.progress_pct,
        total_items=run.total_items,
        duplicates_found=run.duplicates_found,
        near_duplicates_found=run.near_duplicates_found,
        unique_items=run.unique_items,
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.get("/status/{run_id}", response_model=PipelineStatusResponse)
def get_pipeline_status(run_id: int, db: Session = Depends(get_db)):
    """Poll the current status of a pipeline run."""
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Pipeline run {run_id} not found")

    return PipelineStatusResponse(
        id=run.id,
        upload_session_id=run.upload_session_id,
        status=run.status,
        current_step=run.current_step,
        progress_pct=run.progress_pct,
        total_items=run.total_items,
        duplicates_found=run.duplicates_found,
        near_duplicates_found=run.near_duplicates_found,
        unique_items=run.unique_items,
        error_message=run.error_message,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.get("/history", response_model=List[PipelineStatusResponse])
def get_pipeline_history(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """List all pipeline runs, most recent first."""
    runs = (
        db.query(PipelineRun)
        .order_by(PipelineRun.started_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        PipelineStatusResponse(
            id=r.id,
            upload_session_id=r.upload_session_id,
            status=r.status,
            current_step=r.current_step,
            progress_pct=r.progress_pct,
            total_items=r.total_items,
            duplicates_found=r.duplicates_found,
            near_duplicates_found=r.near_duplicates_found,
            unique_items=r.unique_items,
            error_message=r.error_message,
            started_at=r.started_at,
            completed_at=r.completed_at,
        )
        for r in runs
    ]


async def _execute_pipeline_batch(run_ids: List[int], dup_threshold: float, near_dup_threshold: float):
    """
    Background task that delegates to the full pipeline orchestrator.
    Processes multiple pipeline runs sequentially to ensure vector DB integrity.
    """
    from app.services.pipeline import execute
    
    for run_id in run_ids:
        logger.info(f"🚀 Starting background pipeline run {run_id} (Dups: >{dup_threshold}, Near: {near_dup_threshold}-{dup_threshold})")
        try:
            execute(run_id, dup_threshold, near_dup_threshold)
            logger.info(f"✅ Background pipeline run {run_id} finished successfully!")
        except Exception as e:
            logger.error(f"❌ Background pipeline run {run_id} FAILED: {str(e)}", exc_info=True)

"""
UniMat AI — Pipeline Router

Triggers and monitors the AI processing pipeline.
"""

import asyncio
from typing import List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PipelineRun, UploadSession, PipelineStatus
from app.schemas import PipelineRunRequest, PipelineStatusResponse

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

        # Schedule background processing (actual implementation in Phase 2)
        background_tasks.add_task(
            _execute_pipeline, 
            run.id, 
            request.dup_threshold, 
            request.near_dup_threshold
        )

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

    return pipeline_runs


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


async def _execute_pipeline(run_id: int, dup_threshold: float = 0.95, near_dup_threshold: float = 0.85):
    """
    Background task that delegates to the full pipeline orchestrator.
    
    Pipeline steps:
    1. NLP Standardization (spaCy + Regex)
    2. Vector Embedding (ChromaDB + BGE)
    3. Tri-State Classification
    4. LLM Batch Code Generation (Gemini)
    5. Persist results to PostgreSQL
    """
    from app.services.pipeline import execute
    execute(run_id, dup_threshold, near_dup_threshold)


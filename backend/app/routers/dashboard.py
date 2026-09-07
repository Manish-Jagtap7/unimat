"""
UniMat AI — Dashboard Router

Aggregated statistics and analytics for the "One Nation" dashboard.
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import (
    MaterialItem, NationalCode, UploadSession, CPSEProfile,
    AuditTrail, Classification, ReviewStatus, PipelineStatus,
)
from app.schemas import DashboardResponse, DashboardStats, RecentActivity

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardResponse)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    Get aggregated dashboard statistics.
    
    Returns:
    - Overview metrics (total items, CNMCs, reduction %)
    - Classification distribution
    - Recent upload activity
    """
    # ─── Total Counts ───────────────────────────────────────────────────────────
    total_materials = db.query(MaterialItem).count()
    total_cnmc_codes = db.query(NationalCode).count()
    cpse_count = db.query(CPSEProfile).count()

    # ─── Classification Breakdown ───────────────────────────────────────────────
    total_duplicates = (
        db.query(MaterialItem)
        .filter(MaterialItem.classification == Classification.DUPLICATE)
        .count()
    )
    total_near_duplicates = (
        db.query(MaterialItem)
        .filter(MaterialItem.classification == Classification.NEAR_DUPLICATE)
        .count()
    )
    total_unique = (
        db.query(MaterialItem)
        .filter(MaterialItem.classification == Classification.UNIQUE)
        .count()
    )

    # ─── Pending Reviews ────────────────────────────────────────────────────────
    pending_reviews = (
        db.query(MaterialItem)
        .filter(
            MaterialItem.classification == Classification.NEAR_DUPLICATE,
            MaterialItem.review_status == ReviewStatus.PENDING,
        )
        .count()
    )

    # ─── Duplicate Reduction % ──────────────────────────────────────────────────
    duplicate_reduction_pct = 0.0
    if total_materials > 0:
        duplicate_reduction_pct = round(
            (total_duplicates / total_materials) * 100, 1
        )

    # ─── Overall Accuracy Score ────────────────────────────────────────────────
    avg_accuracy = db.query(func.avg(UploadSession.accuracy_score)).scalar()
    average_accuracy = round(avg_accuracy * 100, 1) if avg_accuracy is not None else None

    # ─── Classification Distribution ────────────────────────────────────────────
    classified = total_duplicates + total_near_duplicates + total_unique
    classification_distribution = {
        "DUPLICATE": total_duplicates,
        "NEAR_DUPLICATE": total_near_duplicates,
        "UNIQUE": total_unique,
        "UNPROCESSED": total_materials - classified,
    }

    # ─── Recent Activity ────────────────────────────────────────────────────────
    recent_sessions = (
        db.query(UploadSession)
        .order_by(UploadSession.created_at.desc())
        .limit(10)
        .all()
    )

    recent_activity = []
    for s in recent_sessions:
        cpse = db.query(CPSEProfile).filter(CPSEProfile.id == s.cpse_id).first()
        recent_activity.append(RecentActivity(
            id=s.id,
            cpse_code=cpse.code if cpse else "UNKNOWN",
            filename=s.original_filename,
            row_count=s.row_count,
            status=s.status,
            created_at=s.created_at,
        ))

    # ─── Build Response ─────────────────────────────────────────────────────────
    stats = DashboardStats(
        total_materials=total_materials,
        total_cnmc_codes=total_cnmc_codes,
        total_duplicates=total_duplicates,
        total_near_duplicates=total_near_duplicates,
        total_unique=total_unique,
        duplicate_reduction_pct=duplicate_reduction_pct,
        pending_reviews=pending_reviews,
        cpse_count=cpse_count,
        average_accuracy=average_accuracy,
    )

    return DashboardResponse(
        stats=stats,
        recent_activity=recent_activity,
        classification_distribution=classification_distribution,
    )

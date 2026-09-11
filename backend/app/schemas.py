"""
UniMat AI — Pydantic Schemas

Request/Response models for all API endpoints.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from app.models import Classification, PipelineStatus, ReviewAction, ReviewStatus


# ═══════════════════════════════════════════════════════════════════════════════
# CPSE Profile
# ═══════════════════════════════════════════════════════════════════════════════

class CPSEProfileBase(BaseModel):
    name: str
    code: str
    sector: Optional[str] = None


class CPSEProfileCreate(CPSEProfileBase):
    pass


class CPSEProfileResponse(CPSEProfileBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════════════
# Upload Session
# ═══════════════════════════════════════════════════════════════════════════════

class UploadFileInfo(BaseModel):
    """Metadata for a single uploaded file."""
    cpse_code: str = Field(..., description="CPSE code (e.g., 'IOCL', 'ONGC')")


class UploadSessionResponse(BaseModel):
    id: int
    cpse_code: str
    filename: str
    original_filename: str
    row_count: int
    status: PipelineStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    """Response after multi-file upload."""
    message: str
    sessions: List[UploadSessionResponse]
    total_rows: int


# ═══════════════════════════════════════════════════════════════════════════════
# Material Item
# ═══════════════════════════════════════════════════════════════════════════════

class MaterialItemResponse(BaseModel):
    id: int
    cpse_source: str
    legacy_item_code: Optional[str] = None
    raw_description: str
    uom: Optional[str] = None
    parsed_string: Optional[str] = None
    classification: Optional[Classification] = None
    similarity_score: Optional[float] = None
    matched_cnmc_id: Optional[int] = None
    matched_material_id: Optional[int] = None
    cnmc_code: Optional[str] = None
    standardized_description: Optional[str] = None
    review_status: Optional[ReviewStatus] = None
    cluster_number: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MaterialListResponse(BaseModel):
    items: List[MaterialItemResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ═══════════════════════════════════════════════════════════════════════════════
# National Code (CNMC)
# ═══════════════════════════════════════════════════════════════════════════════

class NationalCodeResponse(BaseModel):
    id: int
    cnmc_code: str
    standardized_description: str
    category: Optional[str] = None
    source: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════════════
# Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

class PipelineRunRequest(BaseModel):
    session_ids: List[int] = Field(..., description="Upload session IDs to process")
    dup_threshold: Optional[float] = None
    near_dup_threshold: Optional[float] = None


class PipelineStatusResponse(BaseModel):
    id: int
    upload_session_id: int
    status: PipelineStatus
    current_step: Optional[str] = None
    progress_pct: float
    total_items: int
    duplicates_found: int
    near_duplicates_found: int
    unique_items: int
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ═══════════════════════════════════════════════════════════════════════════════
# Dashboard
# ═══════════════════════════════════════════════════════════════════════════════

class DashboardStats(BaseModel):
    total_materials: int
    total_cnmc_codes: int
    total_duplicates: int
    total_near_duplicates: int
    total_unique: int
    duplicate_reduction_pct: float
    pending_reviews: int
    cpse_count: int
    average_accuracy: Optional[float] = None


class RecentActivity(BaseModel):
    id: int
    cpse_code: str
    filename: str
    row_count: int
    status: PipelineStatus
    accuracy_score: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DashboardResponse(BaseModel):
    stats: DashboardStats
    recent_activity: List[RecentActivity]
    classification_distribution: dict


# ═══════════════════════════════════════════════════════════════════════════════
# HITL Review
# ═══════════════════════════════════════════════════════════════════════════════

class ReviewItemResponse(BaseModel):
    """A near-duplicate item pending review."""
    material_item: MaterialItemResponse
    candidate_cnmc: Optional[NationalCodeResponse] = None
    similarity_score: float


class ReviewResolveRequest(BaseModel):
    """Request to resolve a near-duplicate review."""
    action: ReviewAction
    officer_name: str = Field(..., min_length=1, max_length=100)
    reason: Optional[str] = None
    override_cnmc_code: Optional[str] = Field(
        None, description="Required when action is OVERRIDE"
    )
    override_description: Optional[str] = Field(
        None, description="Required when action is OVERRIDE"
    )

class BulkApproveRequest(BaseModel):
    item_ids: List[int]
    officer_name: str


class ReviewResolveResponse(BaseModel):
    message: str
    audit_id: int
    material_item_id: int
    action: ReviewAction


# ═══════════════════════════════════════════════════════════════════════════════
# Audit Trail
# ═══════════════════════════════════════════════════════════════════════════════

class AuditTrailResponse(BaseModel):
    id: int
    material_item_id: int
    action: ReviewAction
    old_cnmc_code: Optional[str] = None
    new_cnmc_code: Optional[str] = None
    officer_name: str
    reason: Optional[str] = None
    timestamp: datetime

    model_config = {"from_attributes": True}


class AuditListResponse(BaseModel):
    entries: List[AuditTrailResponse]
    total: int


# ═══════════════════════════════════════════════════════════════════════════════
# Health Check
# ═══════════════════════════════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    vector_db: str

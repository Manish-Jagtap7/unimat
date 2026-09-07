"""
UniMat AI — SQLAlchemy ORM Models

Defines the full database schema for material master management,
CPSE tracking, CNMC codes, HITL review, and audit trail.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, Boolean,
    ForeignKey, Enum as SAEnum, Index,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ─── Enumerations ───────────────────────────────────────────────────────────────

class Classification(str, enum.Enum):
    """Tri-State classification for material items."""
    UNIQUE = "UNIQUE"
    NEAR_DUPLICATE = "NEAR_DUPLICATE"
    DUPLICATE = "DUPLICATE"


class PipelineStatus(str, enum.Enum):
    """Status of a pipeline run."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReviewAction(str, enum.Enum):
    """Actions available in the HITL review workflow."""
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    OVERRIDE = "OVERRIDE"


class ReviewStatus(str, enum.Enum):
    """Status of a review item."""
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"


# ─── CPSE Profile ──────────────────────────────────────────────────────────────

class CPSEProfile(Base):
    """Registered Central Public Sector Enterprise."""
    __tablename__ = "cpse_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)  # e.g., "Indian Oil Corporation Limited"
    code = Column(String(20), unique=True, nullable=False)   # e.g., "IOCL"
    sector = Column(String(50), nullable=True)               # e.g., "Oil & Gas"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    upload_sessions = relationship("UploadSession", back_populates="cpse")


# ─── Upload Session ─────────────────────────────────────────────────────────────

class UploadSession(Base):
    """Tracks each file upload batch from a CPSE."""
    __tablename__ = "upload_sessions"

    id = Column(Integer, primary_key=True, index=True)
    cpse_id = Column(Integer, ForeignKey("cpse_profiles.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    row_count = Column(Integer, default=0)
    status = Column(SAEnum(PipelineStatus), default=PipelineStatus.PENDING)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    accuracy_score = Column(Float, nullable=True)

    # Relationships
    cpse = relationship("CPSEProfile", back_populates="upload_sessions")
    material_items = relationship("MaterialItem", back_populates="upload_session")


# ─── National Code (CNMC) ──────────────────────────────────────────────────────

class NationalCode(Base):
    """Common National Material Code — the unified 'One Nation' code."""
    __tablename__ = "national_codes"

    id = Column(Integer, primary_key=True, index=True)
    cnmc_code = Column(String(50), unique=True, nullable=False, index=True)
    standardized_description = Column(Text, nullable=False)
    category = Column(String(100), nullable=True)
    source = Column(String(20), default="LLM")  # "LLM" or "MANUAL" or "SEED"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    material_items = relationship("MaterialItem", back_populates="national_code")
    legacy_mappings = relationship("LegacyMapping", back_populates="national_code")


# ─── Material Item ──────────────────────────────────────────────────────────────

class MaterialItem(Base):
    """Individual material item ingested from a CPSE upload."""
    __tablename__ = "material_items"

    id = Column(Integer, primary_key=True, index=True)
    upload_session_id = Column(Integer, ForeignKey("upload_sessions.id"), nullable=False)

    # Original data from the uploaded file
    cpse_source = Column(String(20), nullable=False, index=True)
    legacy_item_code = Column(String(100), nullable=True)
    raw_description = Column(Text, nullable=False)
    uom = Column(String(20), nullable=True)
    
    # Ground Truth fields (for evaluation)
    ground_truth_cluster_id = Column(String(100), nullable=True)
    is_duplicate_cluster = Column(Boolean, nullable=True)

    # NLP-processed fields
    parsed_string = Column(Text, nullable=True)

    # Classification results
    classification = Column(SAEnum(Classification), nullable=True, index=True)
    similarity_score = Column(Float, nullable=True)
    matched_cnmc_id = Column(Integer, ForeignKey("national_codes.id"), nullable=True)
    matched_material_id = Column(Integer, ForeignKey("material_items.id"), nullable=True)

    # Review status (for NEAR_DUPLICATE items)
    review_status = Column(SAEnum(ReviewStatus), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    upload_session = relationship("UploadSession", back_populates="material_items")
    national_code = relationship("NationalCode", back_populates="material_items")
    legacy_mapping = relationship("LegacyMapping", back_populates="material_item", uselist=False)
    audit_entries = relationship("AuditTrail", back_populates="material_item")

    # Indexes for common queries
    __table_args__ = (
        Index("ix_material_classification_review", "classification", "review_status"),
    )


# ─── Legacy Mapping ────────────────────────────────────────────────────────────

class LegacyMapping(Base):
    """Maps a CPSE's legacy material code to the unified National Code."""
    __tablename__ = "legacy_mappings"

    id = Column(Integer, primary_key=True, index=True)
    material_item_id = Column(Integer, ForeignKey("material_items.id"), unique=True, nullable=False)
    cnmc_id = Column(Integer, ForeignKey("national_codes.id"), nullable=False)
    cpse_source = Column(String(20), nullable=False)
    legacy_code = Column(String(100), nullable=True)
    mapped_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    material_item = relationship("MaterialItem", back_populates="legacy_mapping")
    national_code = relationship("NationalCode", back_populates="legacy_mappings")


# ─── Audit Trail ───────────────────────────────────────────────────────────────

class AuditTrail(Base):
    """Governance log for all HITL review actions."""
    __tablename__ = "audit_trail"

    id = Column(Integer, primary_key=True, index=True)
    material_item_id = Column(Integer, ForeignKey("material_items.id"), nullable=False)
    action = Column(SAEnum(ReviewAction), nullable=False)
    old_cnmc_id = Column(Integer, ForeignKey("national_codes.id"), nullable=True)
    new_cnmc_id = Column(Integer, ForeignKey("national_codes.id"), nullable=True)
    officer_name = Column(String(100), nullable=False)
    reason = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    material_item = relationship("MaterialItem", back_populates="audit_entries")
    old_national_code = relationship("NationalCode", foreign_keys=[old_cnmc_id])
    new_national_code = relationship("NationalCode", foreign_keys=[new_cnmc_id])


# ─── Pipeline Run ──────────────────────────────────────────────────────────────

class PipelineRun(Base):
    """Tracks each AI pipeline execution."""
    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, index=True)
    upload_session_id = Column(Integer, ForeignKey("upload_sessions.id"), nullable=False)
    status = Column(SAEnum(PipelineStatus), default=PipelineStatus.PENDING)
    current_step = Column(String(50), nullable=True)  # e.g., "NLP", "VECTOR", "CLASSIFY", "LLM"
    progress_pct = Column(Float, default=0.0)
    total_items = Column(Integer, default=0)
    duplicates_found = Column(Integer, default=0)
    near_duplicates_found = Column(Integer, default=0)
    unique_items = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    upload_session = relationship("UploadSession")

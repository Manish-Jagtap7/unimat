"""
UniMat AI — Upload Router

Handles multi-file CPSE ingestion with per-file CPSE source tracking.
"""

import os
import uuid
from datetime import datetime, timezone
from typing import List

import pandas as pd
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_settings
from app.models import CPSEProfile, UploadSession, MaterialItem, PipelineStatus
from app.schemas import UploadResponse, UploadSessionResponse

router = APIRouter(prefix="/api/upload", tags=["Upload"])
settings = get_settings()

# ─── Default CPSE Registry ─────────────────────────────────────────────────────
DEFAULT_CPSES = {
    "IOCL": ("Indian Oil Corporation Limited", "Oil & Gas"),
    "ONGC": ("Oil and Natural Gas Corporation", "Oil & Gas"),
    "BPCL": ("Bharat Petroleum Corporation Limited", "Oil & Gas"),
    "HPCL": ("Hindustan Petroleum Corporation Limited", "Oil & Gas"),
    "GAIL": ("GAIL (India) Limited", "Oil & Gas"),
    "CPCL": ("Chennai Petroleum Corporation Limited", "Oil & Gas"),
    "NTPC": ("NTPC Limited", "Power"),
    "SAIL": ("Steel Authority of India Limited", "Steel"),
    "CIL": ("Coal India Limited", "Mining"),
    "BHEL": ("Bharat Heavy Electricals Limited", "Heavy Engineering"),
}


def ensure_cpse_exists(db: Session, cpse_code: str) -> CPSEProfile:
    """Get or create a CPSE profile."""
    cpse = db.query(CPSEProfile).filter(CPSEProfile.code == cpse_code.upper()).first()
    if not cpse:
        default_info = DEFAULT_CPSES.get(cpse_code.upper(), (cpse_code.upper(), "Other"))
        cpse = CPSEProfile(
            name=default_info[0],
            code=cpse_code.upper(),
            sector=default_info[1],
        )
        db.add(cpse)
        db.commit()
        db.refresh(cpse)
    return cpse


@router.post("", response_model=UploadResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    cpse_codes: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    """
    Upload multiple Excel/CSV files simultaneously.
    
    CPSE codes are auto-detected from the 'CPSE_Source' column inside the file.
    If no such column exists, falls back to cpse_codes provided in the form.
    """

    # Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    sessions = []
    total_rows = 0
    seen_cluster_ids = set()

    for idx, file in enumerate(files):
        # Validate file type
        if not file.filename:
            raise HTTPException(status_code=400, detail="File must have a filename")
        
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in ("xlsx", "xls", "csv"):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: .{ext}. Use .xlsx, .xls, or .csv",
            )

        # Save file to disk first so we can read it
        saved_filename = f"{uuid.uuid4().hex}_{file.filename}"
        file_path = os.path.join(settings.UPLOAD_DIR, saved_filename)
        
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # Parse the file
        try:
            if ext == "csv":
                df = pd.read_csv(file_path)
            else:
                df = pd.read_excel(file_path, engine="openpyxl")
        except Exception as e:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=f"Failed to parse {file.filename}: {e}")

        # Auto-detect CPSE from CPSE_Source column inside the file
        cpse_code = None
        if "CPSE_Source" in df.columns:
            first_valid = df["CPSE_Source"].dropna().astype(str).str.strip().str.upper()
            if len(first_valid) > 0:
                cpse_code = first_valid.iloc[0]
        
        # Fallback to form-provided cpse_codes
        if not cpse_code and idx < len(cpse_codes):
            cpse_code = cpse_codes[idx].upper().strip()
        
        # Last resort: extract from filename
        if not cpse_code:
            cpse_code = file.filename.split("_")[0].upper()

        # Ensure CPSE profile exists
        cpse = ensure_cpse_exists(db, cpse_code)

        # Validate required columns
        required_cols = {"Raw_Description"}
        if not required_cols.issubset(set(df.columns)):
            os.remove(file_path)
            raise HTTPException(
                status_code=400,
                detail=f"File {file.filename} missing required column(s): {required_cols - set(df.columns)}",
            )

        # Drop rows with no description
        df = df.dropna(subset=["Raw_Description"]).copy()

        # Create upload session
        session = UploadSession(
            cpse_id=cpse.id,
            filename=saved_filename,
            original_filename=file.filename,
            row_count=len(df),
            status=PipelineStatus.PENDING,
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # Ingest material items
        items = []
        for _, row in df.iterrows():
            # Use per-row CPSE_Source if available, else fall back to the file-level code
            row_cpse = str(row.get("CPSE_Source", cpse_code)).upper().strip()
            if not row_cpse or row_cpse == "NAN":
                row_cpse = cpse_code.upper()

            # Parse Ground Truth columns if they exist
            gt_cluster_id = str(row.get("Ground_Truth_Cluster_ID", "")).strip() if pd.notna(row.get("Ground_Truth_Cluster_ID")) else None
            
            is_dup_cluster = None
            if gt_cluster_id:
                if gt_cluster_id in seen_cluster_ids:
                    # We've seen this cluster before, so this item SHOULD be a duplicate of the previous one
                    is_dup_cluster = True
                else:
                    # First time seeing this cluster, so this item SHOULD be unique
                    is_dup_cluster = False
                    seen_cluster_ids.add(gt_cluster_id)

            item = MaterialItem(
                upload_session_id=session.id,
                cpse_source=row_cpse,
                legacy_item_code=str(row.get("Legacy_Item_Code", "")) if pd.notna(row.get("Legacy_Item_Code")) else None,
                raw_description=str(row["Raw_Description"]),
                uom=str(row.get("UOM", "")) if pd.notna(row.get("UOM")) else None,
                ground_truth_cluster_id=gt_cluster_id,
                is_duplicate_cluster=is_dup_cluster,
            )
            items.append(item)

        db.bulk_save_objects(items)
        db.commit()

        total_rows += len(df)
        sessions.append(UploadSessionResponse(
            id=session.id,
            cpse_code=cpse.code,
            filename=saved_filename,
            original_filename=file.filename,
            row_count=len(df),
            status=session.status,
            accuracy_score=session.accuracy_score,
            created_at=session.created_at,
        ))

    return UploadResponse(
        message=f"Successfully uploaded {len(files)} file(s) with {total_rows} total rows",
        sessions=sessions,
        total_rows=total_rows,
    )


@router.get("/sessions", response_model=List[UploadSessionResponse])
def list_upload_sessions(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List all upload sessions, most recent first."""
    sessions = (
        db.query(UploadSession)
        .order_by(UploadSession.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    results = []
    for s in sessions:
        cpse = db.query(CPSEProfile).filter(CPSEProfile.id == s.cpse_id).first()
        results.append(UploadSessionResponse(
            id=s.id,
            cpse_code=cpse.code if cpse else "UNKNOWN",
            filename=s.filename,
            original_filename=s.original_filename,
            row_count=s.row_count,
            status=s.status,
            accuracy_score=s.accuracy_score,
            created_at=s.created_at,
        ))
    return results

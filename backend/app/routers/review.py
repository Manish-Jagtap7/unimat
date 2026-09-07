"""
UniMat AI — Review Router (HITL)

Human-in-the-Loop review workflow for Near-Duplicate material items.
Fulfills the "Audit trail and governance mechanism" requirement.
"""

from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    MaterialItem, NationalCode, LegacyMapping, AuditTrail,
    Classification, ReviewStatus, ReviewAction,
)
from app.schemas import (
    ReviewItemResponse, ReviewResolveRequest, ReviewResolveResponse,
    MaterialItemResponse, NationalCodeResponse, AuditTrailResponse, AuditListResponse,
    BulkApproveRequest
)

router = APIRouter(prefix="/api/review", tags=["Review"])


@router.get("/pending", response_model=List[ReviewItemResponse])
def get_pending_reviews(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """
    List all Near-Duplicate items awaiting HITL review.
    
    Returns items with their candidate CNMC match for side-by-side comparison.
    """
    items = (
        db.query(MaterialItem)
        .filter(
            MaterialItem.classification == Classification.NEAR_DUPLICATE,
            MaterialItem.review_status == ReviewStatus.PENDING,
        )
        .order_by(MaterialItem.similarity_score.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    results = []
    for item in items:
        # Resolve candidate CNMC
        candidate = None
        if item.matched_cnmc_id:
            nc = db.query(NationalCode).filter(NationalCode.id == item.matched_cnmc_id).first()
            if nc:
                candidate = NationalCodeResponse(
                    id=nc.id,
                    cnmc_code=nc.cnmc_code,
                    standardized_description=nc.standardized_description,
                    category=nc.category,
                    source=nc.source,
                    created_at=nc.created_at,
                )

        results.append(ReviewItemResponse(
            material_item=MaterialItemResponse(
                id=item.id,
                cpse_source=item.cpse_source,
                legacy_item_code=item.legacy_item_code,
                raw_description=item.raw_description,
                uom=item.uom,
                parsed_string=item.parsed_string,
                classification=item.classification,
                similarity_score=item.similarity_score,
                cnmc_code=candidate.cnmc_code if candidate else None,
                standardized_description=candidate.standardized_description if candidate else None,
                review_status=item.review_status,
                created_at=item.created_at,
            ),
            candidate_cnmc=candidate,
            similarity_score=item.similarity_score or 0.0,
        ))

    return results


@router.post("/{item_id}/resolve", response_model=ReviewResolveResponse)
def resolve_review(
    item_id: int,
    request: ReviewResolveRequest,
    db: Session = Depends(get_db),
):
    """
    Resolve a Near-Duplicate review.
    
    Actions:
    - APPROVE: Merge the item into the candidate CNMC.
    - REJECT: Mark as unique; will be sent for new CNMC generation.
    - OVERRIDE: Manually assign a custom CNMC code.
    """
    item = db.query(MaterialItem).filter(MaterialItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Material item not found")

    if item.review_status == ReviewStatus.RESOLVED:
        raise HTTPException(status_code=409, detail="This item has already been resolved")

    old_cnmc_id = item.matched_cnmc_id
    new_cnmc_id = None

    if request.action == ReviewAction.APPROVE:
        # Approve the merge — map to the candidate CNMC
        if not item.matched_cnmc_id:
            raise HTTPException(status_code=400, detail="No candidate CNMC to approve")

        new_cnmc_id = item.matched_cnmc_id

        # Create legacy mapping
        mapping = LegacyMapping(
            material_item_id=item.id,
            cnmc_id=new_cnmc_id,
            cpse_source=item.cpse_source,
            legacy_code=item.legacy_item_code,
        )
        db.add(mapping)

        # Update item classification to DUPLICATE (confirmed by human)
        item.classification = Classification.DUPLICATE
        item.review_status = ReviewStatus.RESOLVED

    elif request.action == ReviewAction.REJECT:
        # Reject the merge — reclassify as UNIQUE for new CNMC generation
        item.classification = Classification.UNIQUE
        item.matched_cnmc_id = None
        item.review_status = ReviewStatus.RESOLVED

    elif request.action == ReviewAction.OVERRIDE:
        # Manual override — create or find the specified CNMC
        if not request.override_cnmc_code or not request.override_description:
            raise HTTPException(
                status_code=400,
                detail="override_cnmc_code and override_description are required for OVERRIDE action",
            )

        # Check if CNMC already exists
        existing = db.query(NationalCode).filter(
            NationalCode.cnmc_code == request.override_cnmc_code
        ).first()

        if existing:
            new_cnmc_id = existing.id
        else:
            new_nc = NationalCode(
                cnmc_code=request.override_cnmc_code,
                standardized_description=request.override_description,
                source="MANUAL",
            )
            db.add(new_nc)
            db.flush()
            new_cnmc_id = new_nc.id

        item.matched_cnmc_id = new_cnmc_id
        item.classification = Classification.DUPLICATE
        item.review_status = ReviewStatus.RESOLVED

        # Create legacy mapping
        mapping = LegacyMapping(
            material_item_id=item.id,
            cnmc_id=new_cnmc_id,
            cpse_source=item.cpse_source,
            legacy_code=item.legacy_item_code,
        )
        db.add(mapping)

    # Create audit trail entry
    audit = AuditTrail(
        material_item_id=item.id,
        action=request.action,
        old_cnmc_id=old_cnmc_id,
        new_cnmc_id=new_cnmc_id,
        officer_name=request.officer_name,
        reason=request.reason,
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)

    return ReviewResolveResponse(
        message=f"Review resolved: {request.action.value}",
        audit_id=audit.id,
        material_item_id=item.id,
        action=request.action,
    )


@router.get("/audit", response_model=AuditListResponse)
def get_audit_trail(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Get the full audit trail of all HITL review actions."""
    total = db.query(AuditTrail).count()
    entries = (
        db.query(AuditTrail)
        .order_by(AuditTrail.timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    results = []
    for entry in entries:
        old_code = None
        new_code = None
        if entry.old_cnmc_id:
            nc = db.query(NationalCode).filter(NationalCode.id == entry.old_cnmc_id).first()
            old_code = nc.cnmc_code if nc else None
        if entry.new_cnmc_id:
            nc = db.query(NationalCode).filter(NationalCode.id == entry.new_cnmc_id).first()
            new_code = nc.cnmc_code if nc else None

        results.append(AuditTrailResponse(
            id=entry.id,
            material_item_id=entry.material_item_id,
            action=entry.action,
            old_cnmc_code=old_code,
            new_cnmc_code=new_code,
            officer_name=entry.officer_name,
            reason=entry.reason,
            timestamp=entry.timestamp,
        ))

    return AuditListResponse(entries=results, total=total)


@router.post("/bulk-approve")
def bulk_approve(
    request: BulkApproveRequest,
    db: Session = Depends(get_db),
):
    """
    Instantly mark a batch of NEAR_DUPLICATE items as DUPLICATE, 
    bypassing the manual HITL side-by-side review.
    """
    items = db.query(MaterialItem).filter(MaterialItem.id.in_(request.item_ids)).all()
    if not items:
        raise HTTPException(status_code=404, detail="No items found")

    processed = 0
    for item in items:
        if item.classification == Classification.NEAR_DUPLICATE and item.review_status == ReviewStatus.PENDING:
            item.classification = Classification.DUPLICATE
            item.review_status = ReviewStatus.RESOLVED

            # If it has a matched CNMC candidate, officially link it
            if item.matched_cnmc_id:
                mapping = LegacyMapping(
                    material_item_id=item.id,
                    cnmc_id=item.matched_cnmc_id,
                    cpse_source=item.cpse_source,
                    legacy_code=item.legacy_item_code,
                )
                db.add(mapping)

            # Audit trail
            audit = AuditTrail(
                material_item_id=item.id,
                action=ReviewAction.APPROVE,
                officer_name=request.officer_name,
                reason="Bulk Approved from Materials Dashboard",
            )
            db.add(audit)
            processed += 1

    db.commit()
    return {"message": f"Successfully bulk approved {processed} items."}

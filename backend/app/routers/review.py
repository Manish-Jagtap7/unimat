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
    BulkApproveRequest, ClusterReviewResponse, ClusterResolveRequest, ClusterAction
)

router = APIRouter(prefix="/api/review", tags=["Review"])


@router.get("/clusters/pending", response_model=List[ClusterReviewResponse])
def get_pending_clusters(db: Session = Depends(get_db)):
    """
    Fetch all clusters that have at least one item pending review.
    """
    pending_children = (
        db.query(MaterialItem)
        .filter(
            MaterialItem.classification == Classification.NEAR_DUPLICATE,
            MaterialItem.review_status == ReviewStatus.PENDING,
        )
        .all()
    )
    
    cluster_root_ids = list(set([child.matched_material_id for child in pending_children if child.matched_material_id]))
    
    results = []
    for root_id in cluster_root_ids:
        root_item = db.query(MaterialItem).filter(MaterialItem.id == root_id).first()
        if not root_item: continue
        
        children = db.query(MaterialItem).filter(MaterialItem.matched_material_id == root_id).all()
        
        candidate = None
        if root_item.matched_cnmc_id:
            nc = db.query(NationalCode).filter(NationalCode.id == root_item.matched_cnmc_id).first()
            if nc:
                candidate = NationalCodeResponse(
                    id=nc.id,
                    cnmc_code=nc.cnmc_code,
                    standardized_description=nc.standardized_description,
                    category=nc.category,
                    source=nc.source,
                    created_at=nc.created_at,
                )
                
        def to_response(item):
            return MaterialItemResponse(
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
            )
            
        results.append(ClusterReviewResponse(
            root_item=to_response(root_item),
            children=[to_response(c) for c in children],
            candidate_cnmc=candidate
        ))
        
    return results


@router.post("/cluster/{cluster_id}/resolve")
def resolve_cluster(
    cluster_id: int,
    request: ClusterResolveRequest,
    db: Session = Depends(get_db),
):
    """
    Resolve a full cluster review.
    """
    root_item = db.query(MaterialItem).filter(MaterialItem.id == cluster_id).first()
    if not root_item:
        raise HTTPException(status_code=404, detail="Cluster root not found")
        
    children = db.query(MaterialItem).filter(MaterialItem.matched_material_id == cluster_id).all()
    
    if request.edited_name and root_item.matched_cnmc_id:
        nc = db.query(NationalCode).filter(NationalCode.id == root_item.matched_cnmc_id).first()
        if nc:
            nc.standardized_description = request.edited_name
            db.add(nc)

    if request.action == ClusterAction.APPROVE:
        for child in children:
            child.review_status = ReviewStatus.RESOLVED
            child.similarity_score = None # Clear percentage
            child.classification = Classification.DUPLICATE
            
    elif request.action == ClusterAction.RECONSTRUCT:
        for child in children:
            if request.removed_item_ids and child.id in request.removed_item_ids:
                child.classification = Classification.UNIQUE
                child.matched_material_id = None
                child.matched_cnmc_id = None
                child.similarity_score = None
                child.review_status = None
            else:
                child.review_status = ReviewStatus.RESOLVED
                child.similarity_score = None
                child.classification = Classification.DUPLICATE

    root_item.review_status = ReviewStatus.RESOLVED
    db.commit()
    
    return {"message": f"Cluster resolved: {request.action.value}"}


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

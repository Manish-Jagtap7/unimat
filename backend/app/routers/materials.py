"""
UniMat AI — Materials Router

Provides paginated, filterable access to material items.
"""

from typing import Optional, List

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from app.database import get_db, SessionLocal
from app.models import MaterialItem, NationalCode, Classification, ReviewStatus, LegacyMapping
from app.schemas import MaterialItemResponse, MaterialListResponse
from app.services import llm_service

logger = logging.getLogger("unimat.materials")

router = APIRouter(prefix="/api/materials", tags=["Materials"])


@router.get("", response_model=MaterialListResponse)
def list_materials(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    filter_mode: Optional[str] = Query(None, pattern="^(CLUSTER|UNIQUE)$"),
    cpse_source: Optional[str] = None,
    session_id: Optional[int] = None,
    search: Optional[str] = None,
    sort_by: str = Query("id", pattern="^(id|cpse_source|classification|similarity_score|created_at)$"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    """
    List material items with cluster-aware filtering.
    
    filter_mode:
    - None / omit: return all items
    - CLUSTER: return items that belong to a cluster (parent + children)
    - UNIQUE: return only true singletons (no parent, no children)
    """
    from sqlalchemy import or_

    # First, find ALL parent IDs (items that have at least one child pointing to them)
    parent_ids_subq = (
        db.query(MaterialItem.matched_material_id)
        .filter(MaterialItem.matched_material_id.isnot(None))
        .distinct()
        .subquery()
    )

    # Build base query
    query = db.query(MaterialItem)

    if filter_mode == "CLUSTER":
        # Items that are either a parent (have children) or a child (have matched_material_id)
        query = query.filter(
            or_(
                MaterialItem.id.in_(parent_ids_subq),
                MaterialItem.matched_material_id.isnot(None),
            )
        )
    elif filter_mode == "UNIQUE":
        # True singletons: not a parent AND not a child
        query = query.filter(
            MaterialItem.id.notin_(parent_ids_subq),
            MaterialItem.matched_material_id.is_(None),
        )

    if cpse_source:
        query = query.filter(MaterialItem.cpse_source == cpse_source.upper())
    if session_id:
        query = query.filter(MaterialItem.upload_session_id == session_id)
    if search:
        query = query.filter(MaterialItem.raw_description.ilike(f"%{search}%"))

    # Total count
    total = query.count()

    # Sort: parents first (matched_material_id IS NULL), then by id
    sort_column = getattr(MaterialItem, sort_by, MaterialItem.id)
    if sort_order == "desc":
        query = query.order_by(MaterialItem.matched_material_id.asc(), sort_column.desc())
    else:
        query = query.order_by(MaterialItem.matched_material_id.asc(), sort_column.asc())

    # Paginate
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()

    # --- Ensure cluster integrity ---
    # If any child was fetched but its parent wasn't, fetch the parent too
    # If any parent was fetched but its children weren't, fetch children too
    fetched_ids = {item.id for item in items}
    missing_parent_ids = set()
    for item in items:
        if item.matched_material_id and item.matched_material_id not in fetched_ids:
            missing_parent_ids.add(item.matched_material_id)

    parent_ids_in_result = {item.id for item in items if item.matched_material_id is None}
    missing_children = (
        db.query(MaterialItem)
        .filter(
            MaterialItem.matched_material_id.in_(list(parent_ids_in_result)),
            MaterialItem.id.notin_(list(fetched_ids)),
        )
        .all()
    ) if parent_ids_in_result else []

    missing_parents = (
        db.query(MaterialItem)
        .filter(MaterialItem.id.in_(list(missing_parent_ids)))
        .all()
    ) if missing_parent_ids else []

    all_items = list(items) + missing_parents + missing_children

    # Assign cluster numbers to parents
    # A parent = item whose ID appears in some child's matched_material_id
    all_child_parent_ids = {item.matched_material_id for item in all_items if item.matched_material_id}
    parent_items_sorted = sorted(
        [item for item in all_items if item.id in all_child_parent_ids],
        key=lambda x: x.id,
    )
    cluster_map = {item.id: idx + 1 for idx, item in enumerate(parent_items_sorted)}

    # Build response
    response_items = []
    for item in all_items:
        cnmc_code = None
        std_desc = None
        if item.matched_cnmc_id:
            nc = db.query(NationalCode).filter(NationalCode.id == item.matched_cnmc_id).first()
            if nc:
                cnmc_code = nc.cnmc_code
                std_desc = nc.standardized_description

        response_items.append(MaterialItemResponse(
            id=item.id,
            cpse_source=item.cpse_source,
            legacy_item_code=item.legacy_item_code,
            raw_description=item.raw_description,
            uom=item.uom,
            parsed_string=item.parsed_string,
            classification=item.classification,
            similarity_score=item.similarity_score,
            matched_cnmc_id=item.matched_cnmc_id,
            matched_material_id=item.matched_material_id,
            cnmc_code=cnmc_code,
            standardized_description=std_desc,
            review_status=item.review_status,
            created_at=item.created_at,
            cluster_number=cluster_map.get(item.id),
        ))

    # Sort: cluster parents first (ascending by cluster_number), children right after parent, singletons last
    def sort_key(resp_item):
        if resp_item.cluster_number is not None:
            # Parent: sort by cluster number, sub-sort 0 to come before children
            return (0, resp_item.cluster_number, 0, resp_item.id)
        elif resp_item.matched_material_id is not None:
            # Child: sort by parent's cluster number, sub-sort 1 to come after parent
            parent_cluster = cluster_map.get(resp_item.matched_material_id, 9999)
            return (0, parent_cluster, 1, resp_item.id)
        else:
            # Singleton: comes last
            return (1, 0, 0, resp_item.id)

    response_items.sort(key=sort_key)

    total_pages = (total + page_size - 1) // page_size

    return MaterialListResponse(
        items=response_items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/cpse-sources", response_model=List[str])
def get_cpse_sources(db: Session = Depends(get_db)):
    """Get all distinct CPSE sources in the database."""
    sources = (
        db.query(MaterialItem.cpse_source)
        .distinct()
        .order_by(MaterialItem.cpse_source)
        .all()
    )
    return [s[0] for s in sources]


def _background_generate_names():
    db = SessionLocal()
    try:
        # Find all UNIQUE items (cluster parents / singletons) that do NOT have a matched_cnmc_id
        unassigned_parents = (
            db.query(MaterialItem)
            .filter(
                MaterialItem.classification == Classification.UNIQUE,
                MaterialItem.matched_cnmc_id == None
            )
            .all()
        )

        if not unassigned_parents:
            logger.info("No unassigned items found for LLM generation.")
            return

        logger.info(f"Generating names for {len(unassigned_parents)} clusters...")

        groups = {}
        group_item_map = {}

        for idx, parent in enumerate(unassigned_parents):
            # Fetch all children of this parent
            children = (
                db.query(MaterialItem)
                .filter(MaterialItem.matched_material_id == parent.id)
                .all()
            )
            
            group_id = f"group_{idx}"
            
            # Combine descriptions (deduplicated) to give LLM maximum context for this cluster
            descriptions = [parent.raw_description] + [c.raw_description for c in children]
            groups[group_id] = list(set(descriptions))
            
            # Keep track of the entire cluster so they all get assigned the SAME generated CNMC
            group_item_map[group_id] = [parent] + children

        # Call LLM in batches
        generated_codes = llm_service.generate_codes_batch(groups)

        # Persist generated CNMC codes and update items
        for group_id, code_result in generated_codes.items():
            existing_nc = (
                db.query(NationalCode)
                .filter(NationalCode.cnmc_code == code_result.cnmc_code)
                .first()
            )

            if existing_nc:
                nc = existing_nc
            else:
                nc = NationalCode(
                    cnmc_code=code_result.cnmc_code,
                    standardized_description=code_result.standardized_description,
                    category=code_result.category,
                    source="LLM",
                )
                db.add(nc)
                db.flush()

            # Link items in this group to the CNMC
            for item in group_item_map.get(group_id, []):
                item.matched_cnmc_id = nc.id

                # Create legacy mapping
                mapping = LegacyMapping(
                    material_item_id=item.id,
                    cnmc_id=nc.id,
                    cpse_source=item.cpse_source,
                    legacy_code=item.legacy_item_code,
                )
                db.add(mapping)

        db.commit()
        logger.info(f"Successfully generated names for {len(generated_codes)} distinct items.")
    except Exception as e:
        logger.error(f"Failed background generation: {e}", exc_info=True)
    finally:
        db.close()


@router.post("/generate-names")
def generate_names(background_tasks: BackgroundTasks):
    """
    Trigger background LLM generation for all DUPLICATE/UNIQUE items 
    that currently lack a National Code.
    """
    background_tasks.add_task(_background_generate_names)
    return {"message": "LLM Generation triggered in the background. Check logs for progress."}

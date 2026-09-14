"""
UniMat AI — Pipeline Orchestrator

Coordinates the full AI processing pipeline:
  Step 1: NLP Standardization (spaCy + Regex)
  Step 2: Vector Embedding & Indexing (Qdrant + BGE)
  Step 3: Tri-State Classification (Duplicate / Near-Duplicate / Unique)
  Step 4: LLM Batch Code Generation (Gemini) for Unique items
  Step 5: Persist results to PostgreSQL
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import (
    MaterialItem, NationalCode, LegacyMapping, PipelineRun,
    UploadSession, Classification, PipelineStatus, ReviewStatus,
)
from app.services import nlp_service, vector_service, classifier, llm_service
from app.services.classifier import ClassificationResult

logger = logging.getLogger("unimat.pipeline")


def _update_progress(db: Session, run: PipelineRun, step: str, pct: float):
    """Update pipeline run progress."""
    run.current_step = step
    run.progress_pct = round(pct, 1)
    db.commit()


def execute(run_id: int, dup_threshold: float, near_dup_threshold: float):
    """
    Execute the full AI pipeline for a given pipeline run.
    
    This is called as a background task from the pipeline router.
    It creates its own DB session to avoid threading issues.
    """
    db = SessionLocal()

    try:
        # ─── Load pipeline run ──────────────────────────────────────────────────
        run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
        if not run:
            logger.error(f"Pipeline run {run_id} not found")
            return

        run.status = PipelineStatus.RUNNING
        run.current_step = "INITIALIZING"
        db.commit()

        session_id = run.upload_session_id

        # ─── Load material items for this upload session ────────────────────────
        items = (
            db.query(MaterialItem)
            .filter(MaterialItem.upload_session_id == session_id)
            .all()
        )

        if not items:
            run.status = PipelineStatus.COMPLETED
            run.current_step = "DONE"
            run.progress_pct = 100.0
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            logger.warning(f"No items found for session {session_id}")
            return

        run.total_items = len(items)
        db.commit()

        logger.info(f"Pipeline started for run {run_id}: {len(items)} items")

        # ═════════════════════════════════════════════════════════════════════════
        # STEP 1: NLP Standardization
        # ═════════════════════════════════════════════════════════════════════════
        _update_progress(db, run, "NLP_STANDARDIZATION", 10.0)
        logger.info("Step 1: NLP Standardization")

        for item in items:
            parsed_string, specs = nlp_service.standardize(
                item.raw_description,
                item.uom or "",
            )
            item.parsed_string = parsed_string

        db.commit()
        logger.info(f"Step 1 complete: {len(items)} items standardized")

        # ═════════════════════════════════════════════════════════════════════════
        # STEP 2: Vector Embedding & Indexing
        # ═════════════════════════════════════════════════════════════════════════
        _update_progress(db, run, "VECTOR_EMBEDDING", 30.0)
        logger.info("Step 2: Vector Embedding & Indexing")

        # Prepare data for Qdrant
        vector_ids = [f"item_{item.id}" for item in items]
        vector_docs = [item.parsed_string for item in items]
        vector_metas = [
            {
                "item_id": str(item.id),
                "cpse_source": item.cpse_source,
                "raw_description": item.raw_description[:200],  # Truncate for metadata
            }
            for item in items
        ]

        # ═════════════════════════════════════════════════════════════════════════
        # STEP 2 & 3: Sequential Tri-State Classification & Indexing
        # ═════════════════════════════════════════════════════════════════════════
        _update_progress(db, run, "CLASSIFICATION", 50.0)
        logger.info("Step 2 & 3: Sequential Classification")

        classification_results = []
        for item, vector_id, vector_doc, vector_meta in zip(items, vector_ids, vector_docs, vector_metas):
            # 1. Query existing Qdrant index for nearest neighbors
            match_results = vector_service.query_batch(
                query_texts=[vector_doc],
                query_ids=[vector_id],
                n_results=1,
            )

            # 2. Classify based on similarity scores
            item_dict = {"id": item.id, "parsed_string": item.parsed_string}
            result = classifier.classify_batch(
                [item_dict], 
                match_results,
                dup_threshold,
                near_dup_threshold
            )[0]
            classification_results.append(result)

            # 3. Add item to Qdrant only if it's a new cluster center (UNIQUE)
            if result.classification == Classification.UNIQUE:
                vector_service.add_items([vector_id], [vector_doc], [vector_meta])

        # Build a lookup: vector_id -> item for resolving matched CNMC IDs
        vector_id_to_item = {f"item_{item.id}": item for item in items}
        # Apply classifications to material items
        for result in classification_results:
            item = db.query(MaterialItem).filter(MaterialItem.id == result.item_id).first()
            if not item:
                continue

            item.classification = result.classification
            item.similarity_score = result.similarity_score

            if result.classification in (Classification.NEAR_DUPLICATE, Classification.DUPLICATE):
                if result.classification == Classification.NEAR_DUPLICATE:
                    item.review_status = ReviewStatus.PENDING

                if result.matched_vector_id:
                    matched_item = vector_id_to_item.get(result.matched_vector_id)
                    if not matched_item:
                        try:
                            m_id = int(result.matched_vector_id.replace("item_", ""))
                            matched_item = db.query(MaterialItem).filter(MaterialItem.id == m_id).first()
                        except Exception:
                            pass
                    
                    if matched_item:
                        # Since we only add UNIQUE items to Qdrant, matched_item is guaranteed to be a root parent.
                        item.matched_material_id = matched_item.id
                        
                        if matched_item.matched_cnmc_id:
                            item.matched_cnmc_id = matched_item.matched_cnmc_id

                        if result.classification == Classification.DUPLICATE and matched_item.matched_cnmc_id:
                            mapping = LegacyMapping(
                                material_item_id=item.id,
                                cnmc_id=matched_item.matched_cnmc_id,
                                cpse_source=item.cpse_source,
                                legacy_code=item.legacy_item_code,
                            )
                            db.add(mapping)

        db.commit()

        # Count classifications
        dup_count = sum(1 for r in classification_results if r.classification == Classification.DUPLICATE)
        near_dup_count = sum(1 for r in classification_results if r.classification == Classification.NEAR_DUPLICATE)
        unique_count = sum(1 for r in classification_results if r.classification == Classification.UNIQUE)

        run.duplicates_found = dup_count
        run.near_duplicates_found = near_dup_count
        run.unique_items = unique_count
        db.commit()

        logger.info(
            f"Step 3 complete: DUPLICATE={dup_count}, "
            f"NEAR_DUPLICATE={near_dup_count}, UNIQUE={unique_count}"
        )

        # Step 4 (LLM Generation) is now DEFERRED and triggered on-demand via the frontend.

        # ═════════════════════════════════════════════════════════════════════════
        # STEP 5: Finalize
        # ═════════════════════════════════════════════════════════════════════════
        _update_progress(db, run, "FINALIZING", 95.0)

        # Update upload session status & calculate accuracy
        upload_session = (
            db.query(UploadSession)
            .filter(UploadSession.id == session_id)
            .first()
        )
        if upload_session:
            # Reload items from DB to get the committed classifications.
            # The original `items` list has stale ORM objects with classification=None
            # because line 146 creates new ORM instances during classification writes.
            fresh_items = (
                db.query(MaterialItem)
                .filter(MaterialItem.upload_session_id == session_id)
                .order_by(MaterialItem.id)
                .all()
            )
            
            # Calculate accuracy against ground truth based on cluster vs singleton counts
            items_with_gt = [i for i in fresh_items if i.ground_truth_cluster_id]
            
            if items_with_gt:
                import collections
                # 1. Actual clusters vs singletons
                gt_counts = collections.Counter([str(i.ground_truth_cluster_id).strip() for i in items_with_gt])
                actual_clusters = sum(1 for count in gt_counts.values() if count > 1)
                actual_singletons = sum(1 for count in gt_counts.values() if count == 1)
                
                # 2. AI clusters vs singletons for the CURRENT session
                assigned_cluster_ids = []
                for i in fresh_items:
                    if i.matched_material_id is not None:
                        assigned_cluster_ids.append(i.matched_material_id)
                    else:
                        assigned_cluster_ids.append(i.id)
                
                ai_counts = collections.Counter(assigned_cluster_ids)
                ai_clusters = sum(1 for count in ai_counts.values() if count > 1)
                ai_singletons = sum(1 for count in ai_counts.values() if count == 1)
                
                # 3. Calculate macro-accuracy
                cluster_acc = min(actual_clusters, ai_clusters) / max(actual_clusters, ai_clusters) if max(actual_clusters, ai_clusters) > 0 else 1.0
                singleton_acc = min(actual_singletons, ai_singletons) / max(actual_singletons, ai_singletons) if max(actual_singletons, ai_singletons) > 0 else 1.0
                
                upload_session.accuracy_score = round((cluster_acc + singleton_acc) / 2, 4)
                logger.info(f"Accuracy Metric: (Clusters: {ai_clusters}/{actual_clusters}, Singletons: {ai_singletons}/{actual_singletons}) = {upload_session.accuracy_score * 100:.1f}%")
            else:
                upload_session.accuracy_score = None  # No ground truth data available
                
                
            upload_session.status = PipelineStatus.COMPLETED
            upload_session.completed_at = datetime.now(timezone.utc)

        # Mark pipeline run as completed
        run.status = PipelineStatus.COMPLETED
        run.current_step = "DONE"
        run.progress_pct = 100.0
        run.completed_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            f"Pipeline run {run_id} COMPLETED: "
            f"{run.total_items} items processed, "
            f"{run.duplicates_found} duplicates, "
            f"{run.near_duplicates_found} near-duplicates, "
            f"{run.unique_items} unique"
        )

    except Exception as e:
        logger.error(f"Pipeline run {run_id} FAILED: {e}", exc_info=True)

        try:
            run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
            if run:
                run.status = PipelineStatus.FAILED
                run.error_message = str(e)[:500]
                run.completed_at = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            pass

    finally:
        db.close()

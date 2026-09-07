"""
UniMat AI — Tri-State Classifier

Categorizes material items based on cosine similarity against the ChromaDB index:
  - DUPLICATE (>0.95):       Auto-mapped to existing CNMC.
  - NEAR_DUPLICATE (0.85-0.95): Flagged for HITL review.
  - UNIQUE (<0.85):          Sent to LLM for new CNMC generation.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.config import get_settings
from app.models import Classification

logger = logging.getLogger("unimat.classifier")

settings = get_settings()


@dataclass
class ClassificationResult:
    """Result of classifying a single material item."""
    item_id: int
    classification: Classification
    similarity_score: float
    matched_chroma_id: Optional[str] = None  # ChromaDB document ID of best match
    matched_metadata: Optional[dict] = None


def classify_single(similarity_score: float, dup_threshold: float, near_dup_threshold: float) -> Classification:
    """
    Apply Tri-State classification based on cosine similarity score.
    """
    if similarity_score >= dup_threshold:
        return Classification.DUPLICATE
    elif similarity_score >= near_dup_threshold:
        return Classification.NEAR_DUPLICATE
    else:
        return Classification.UNIQUE


def classify_batch(
    items: List[dict],
    match_results: List[List[Tuple[str, float, dict]]],
    dup_threshold: float = 0.95,
    near_dup_threshold: float = 0.85,
) -> List[ClassificationResult]:
    """
    Classify a batch of material items based on their vector match results.
    
    Args:
        items: List of dicts with at minimum {'id': int, 'parsed_string': str}
        match_results: Corresponding nearest-neighbor results from vector_service.query_batch()
                       Each element is a list of (matched_id, similarity, metadata) tuples.
    
    Returns:
        List of ClassificationResult objects.
    """
    results = []
    
    for item, matches in zip(items, match_results):
        item_id = item["id"]
        
        if not matches:
            # No matches in the index — this is definitely unique
            result = ClassificationResult(
                item_id=item_id,
                classification=Classification.UNIQUE,
                similarity_score=0.0,
                matched_chroma_id=None,
                matched_metadata=None,
            )
        else:
            # Use the best (highest similarity) match
            best_id, best_similarity, best_metadata = matches[0]
            classification = classify_single(best_similarity, dup_threshold, near_dup_threshold)
            
            result = ClassificationResult(
                item_id=item_id,
                classification=classification,
                similarity_score=round(best_similarity, 4),
                matched_chroma_id=best_id,
                matched_metadata=best_metadata,
            )
        
        results.append(result)
    
    # Log classification distribution
    counts = {c: 0 for c in Classification}
    for r in results:
        counts[r.classification] += 1
    
    logger.info(
        f"Classification results: "
        f"DUPLICATE={counts[Classification.DUPLICATE]}, "
        f"NEAR_DUPLICATE={counts[Classification.NEAR_DUPLICATE]}, "
        f"UNIQUE={counts[Classification.UNIQUE]}"
    )
    
    return results


def get_threshold_info() -> dict:
    """Return current classification thresholds for API/dashboard use."""
    return {
        "duplicate_threshold": settings.DUPLICATE_THRESHOLD,
        "near_duplicate_threshold": settings.NEAR_DUPLICATE_THRESHOLD,
        "description": {
            "DUPLICATE": f"Similarity ≥ {settings.DUPLICATE_THRESHOLD} → Auto-mapped to existing CNMC",
            "NEAR_DUPLICATE": f"Similarity {settings.NEAR_DUPLICATE_THRESHOLD}–{settings.DUPLICATE_THRESHOLD} → HITL review",
            "UNIQUE": f"Similarity < {settings.NEAR_DUPLICATE_THRESHOLD} → New CNMC via LLM",
        },
    }

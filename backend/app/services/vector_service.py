"""
UniMat AI — Vector Service (Qdrant Hybrid Search)

UniMat AI — Vector Service
Handles inserting and querying material items in Qdrant using BGE-base dense embeddings.
"""

import logging
from typing import List, Tuple, Optional
import numpy as np

from qdrant_client import QdrantClient, models
from sentence_transformers import SentenceTransformer

from app.config import get_settings

logger = logging.getLogger("unimat.vector")
settings = get_settings()

COLLECTION_NAME = "material_master"
DENSE_VECTOR_SIZE = 768  # BGE-base output dimension

# ─── Singleton Instances ────────────────────────────────────────────────────────
_qdrant_client: Optional[QdrantClient] = None
_dense_model: Optional[SentenceTransformer] = None


def _get_dense_model() -> SentenceTransformer:
    """Lazy-load the SentenceTransformer dense embedding model."""
    global _dense_model
    if _dense_model is None:
        logger.info(f"Loading dense embedding model: {settings.EMBEDDING_MODEL}")
        _dense_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info(f"Dense model loaded (device: {_dense_model.device})")
    return _dense_model


def _get_client() -> QdrantClient:
    """Get or create a persistent Qdrant client."""
    global _qdrant_client
    if _qdrant_client is None:
        logger.info(f"Initializing Qdrant client at: {settings.QDRANT_PATH}")
        _qdrant_client = QdrantClient(path=settings.QDRANT_PATH)
        logger.info("Qdrant client initialized")
    return _qdrant_client


def _ensure_collection():
    """Create the collection if it doesn't exist."""
    client = _get_client()
    
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                "dense": models.VectorParams(
                    size=DENSE_VECTOR_SIZE,
                    distance=models.Distance.COSINE,
                ),
            },
        )
        logger.info(f"Created Qdrant collection '{COLLECTION_NAME}'")
    else:
        logger.info(f"Qdrant collection '{COLLECTION_NAME}' already exists")


def _encode_dense(texts: List[str]) -> np.ndarray:
    """Encode texts into dense vectors using SentenceTransformer."""
    model = _get_dense_model()
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False)


# ─── Public API (same signatures as before) ─────────────────────────────────────

def add_items(ids: List[str], documents: List[str], metadatas: List[dict] = None):
    """
    Add material descriptions to the Qdrant index.
    """
    _ensure_collection()
    client = _get_client()

    dense_vectors = _encode_dense(documents)

    points = []
    for i, doc_id in enumerate(ids):
        payload = metadatas[i] if metadatas else {}
        payload["document"] = documents[i]
        
        point = models.PointStruct(
            id=abs(hash(doc_id)) % (2**63),
            vector={
                "dense": dense_vectors[i].tolist(),
            },
            payload={**payload, "chroma_id": doc_id},
        )
        points.append(point)

    # wait=True ensures vectors are indexed and immediately searchable 
    # before the next sequential pipeline item queries them.
    client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)
    count = client.count(collection_name=COLLECTION_NAME).count
    logger.info(f"Indexed {len(ids)} items in Qdrant (total: {count})")


def query_nearest(
    query_text: str,
    n_results: int = 1,
    exclude_id: str = None,
) -> List[Tuple[str, float, dict]]:
    """
    Find the nearest neighbors using hybrid search (dense + sparse).
    
    Uses RRF for RANKING, then uses a Cross-Encoder Reranker to calculate an absolute 0-1 similarity score.
    """
    _ensure_collection()
    client = _get_client()

    count = client.count(collection_name=COLLECTION_NAME).count
    if count == 0:
        return []

    # Encode query
    query_dense = _encode_dense([query_text])[0]
    sparse_vec_list = _encode_sparse([query_text])
    sparse_vec = sparse_vec_list[0]

    fetch_n = min(n_results + (1 if exclude_id else 0), count)

    # Step 1: Use RRF to RANK candidates (hybrid dense + sparse)
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            models.Prefetch(
                query=query_dense.tolist(),
                using="dense",
                limit=fetch_n + 5,
            ),
            models.Prefetch(
                query=models.SparseVector(
                    indices=sparse_vec.indices.tolist(),
                    values=sparse_vec.values.tolist(),
                ),
                using="sparse",
                limit=fetch_n + 5,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=fetch_n,
        with_payload=True,
    )

    candidate_docs = []
    candidate_points = []
    
    for point in results.points:
        chroma_id = point.payload.get("chroma_id", str(point.id))
        if exclude_id and chroma_id == exclude_id:
            continue
            
        candidate_docs.append(point.payload.get("document", ""))
        candidate_points.append(point)
        
        if len(candidate_points) >= n_results:
            break

    matches = []
    if candidate_points:
        # Step 2: Rerank to find false positives
        logits = _rerank_scores(query_text, candidate_docs)
        
        for idx, point in enumerate(candidate_points):
            chroma_id = point.payload.get("chroma_id", str(point.id))
            
            # Compute actual dense cosine similarity
            match_dense = np.array(point.vector["dense"])
            dense_score = _cosine_similarity(query_dense, match_dense)
            
            logit = float(logits[idx])
            
            # Penalize dense score if reranker strongly disagrees
            if logit < -2.0:
                final_score = dense_score * 0.4
            elif logit < 0.0:
                final_score = dense_score * 0.7
            else:
                final_score = dense_score
                
            metadata = {k: v for k, v in point.payload.items() if k not in ("document", "chroma_id")}
            matches.append((chroma_id, final_score, metadata))

    # Sort matches descending
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches


def query_batch(
    query_texts: List[str],
    query_ids: List[str],
    n_results: int = 1,
) -> List[List[Tuple[str, float, dict]]]:
    """
    Batch query for nearest neighbors, excluding self-matches.
    """
    _ensure_collection()
    client = _get_client()

    count = client.count(collection_name=COLLECTION_NAME).count
    if count == 0:
        return [[] for _ in query_texts]

    dense_vectors = _encode_dense(query_texts)
    all_results = []
    fetch_n = min(n_results + 1, count)

    for q_idx in range(len(query_texts)):
        try:
            results = client.query_points(
                collection_name=COLLECTION_NAME,
                query=dense_vectors[q_idx].tolist(),
                using="dense",
                limit=fetch_n,
                with_payload=True,
            )
        except Exception as e:
            logger.error(f"Qdrant query error for item {query_ids[q_idx]}: {e}")
            all_results.append([])
            continue

        matches = []
        for point in results.points:
            chroma_id = point.payload.get("chroma_id", str(point.id))
            if chroma_id == query_ids[q_idx]:
                continue
                
            similarity = float(point.score)
            metadata = {k: v for k, v in point.payload.items() if k not in ("document", "chroma_id")}
            matches.append((chroma_id, similarity, metadata))
            
            if len(matches) >= n_results:
                break
                
        # Sort descending
        matches.sort(key=lambda x: x[1], reverse=True)
        all_results.append(matches)

    return all_results


def get_index_count() -> int:
    """Get the total number of items in the Qdrant index."""
    _ensure_collection()
    client = _get_client()
    return client.count(collection_name=COLLECTION_NAME).count


def reset_collection():
    """Delete and recreate the collection. Use for testing/reset."""
    client = _get_client()
    try:
        if client.collection_exists(COLLECTION_NAME):
            client.delete_collection(collection_name=COLLECTION_NAME)
            logger.warning(f"Deleted Qdrant collection '{COLLECTION_NAME}'")
    except Exception:
        pass
    _ensure_collection()

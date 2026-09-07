"""
UniMat AI — Vector Service

Manages ChromaDB persistent storage and BAAI/bge-base-en-v1.5 embeddings.
Provides indexing and similarity search for material descriptions.
"""

import logging
from typing import List, Tuple, Optional

import chromadb
from chromadb.utils import embedding_functions

from app.config import get_settings

logger = logging.getLogger("unimat.vector")

settings = get_settings()

# ─── Singleton Instances ────────────────────────────────────────────────────────
_chroma_client: Optional[chromadb.ClientAPI] = None
_embedding_fn = None
_collection = None

COLLECTION_NAME = "material_master"


def _get_embedding_function():
    """Lazy-load the SentenceTransformer embedding function."""
    global _embedding_fn
    if _embedding_fn is None:
        logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
        _embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.EMBEDDING_MODEL,
        )
        logger.info("Embedding model loaded successfully")
    return _embedding_fn


def _get_client() -> chromadb.ClientAPI:
    """Get or create a persistent ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        logger.info(f"Initializing ChromaDB persistent client at: {settings.CHROMA_PERSIST_DIR}")
        _chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        logger.info("ChromaDB client initialized")
    return _chroma_client


def get_collection() -> chromadb.Collection:
    """Get or create the material_master collection."""
    global _collection
    if _collection is None:
        client = _get_client()
        emb_fn = _get_embedding_function()
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=emb_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"ChromaDB collection '{COLLECTION_NAME}' ready (count: {_collection.count()})")
    return _collection


def add_items(ids: List[str], documents: List[str], metadatas: List[dict] = None):
    """
    Add material descriptions to the ChromaDB index.
    
    Args:
        ids: Unique identifiers for each document.
        documents: The parsed/standardized material descriptions.
        metadatas: Optional metadata dicts for each document.
    """
    collection = get_collection()

    # ChromaDB has a batch limit; process in chunks of 500
    batch_size = 500
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i:i + batch_size]
        batch_docs = documents[i:i + batch_size]
        batch_meta = metadatas[i:i + batch_size] if metadatas else None

        collection.upsert(
            ids=batch_ids,
            documents=batch_docs,
            metadatas=batch_meta,
        )

    logger.info(f"Indexed {len(ids)} items in ChromaDB (total: {collection.count()})")


def query_nearest(
    query_text: str,
    n_results: int = 1,
    exclude_id: str = None,
) -> List[Tuple[str, float, dict]]:
    """
    Find the nearest neighbors for a query text.
    
    Args:
        query_text: The standardized material description to search for.
        n_results: Number of results to return.
        exclude_id: Optional ID to exclude from results (self-match prevention).
    
    Returns:
        List of tuples: (matched_id, similarity_score, metadata)
        similarity_score is cosine similarity (1.0 = identical, 0.0 = orthogonal)
    """
    collection = get_collection()

    if collection.count() == 0:
        return []

    # Query with extra results to handle self-exclusion
    fetch_n = n_results + (1 if exclude_id else 0)
    fetch_n = min(fetch_n, collection.count())

    results = collection.query(
        query_texts=[query_text],
        n_results=fetch_n,
        include=["distances", "metadatas", "documents"],
    )

    if not results["ids"] or not results["ids"][0]:
        return []

    matches = []
    for idx, (match_id, distance) in enumerate(zip(results["ids"][0], results["distances"][0])):
        if exclude_id and match_id == exclude_id:
            continue

        # ChromaDB cosine distance = 1 - cosine_similarity
        # So similarity = 1 - distance
        similarity = 1.0 - distance

        metadata = results["metadatas"][0][idx] if results["metadatas"] else {}

        matches.append((match_id, similarity, metadata))

        if len(matches) >= n_results:
            break

    return matches


def query_batch(
    query_texts: List[str],
    query_ids: List[str],
    n_results: int = 1,
) -> List[List[Tuple[str, float, dict]]]:
    """
    Batch query for nearest neighbors, excluding self-matches.
    
    Args:
        query_texts: List of standardized descriptions.
        query_ids: Corresponding IDs to exclude from self-matching.
        n_results: Number of results per query.
    
    Returns:
        List of result lists, one per query.
    """
    collection = get_collection()

    if collection.count() == 0:
        return [[] for _ in query_texts]

    # Process in batches to avoid memory issues
    batch_size = 100
    all_results = []

    for i in range(0, len(query_texts), batch_size):
        batch_texts = query_texts[i:i + batch_size]
        batch_ids = query_ids[i:i + batch_size]

        fetch_n = min(n_results + 1, collection.count())  # +1 for self-exclusion

        results = collection.query(
            query_texts=batch_texts,
            n_results=fetch_n,
            include=["distances", "metadatas"],
        )

        for q_idx in range(len(batch_texts)):
            matches = []
            if results["ids"] and results["ids"][q_idx]:
                for m_idx, (match_id, distance) in enumerate(
                    zip(results["ids"][q_idx], results["distances"][q_idx])
                ):
                    # Skip self-match
                    if match_id == batch_ids[q_idx]:
                        continue

                    similarity = 1.0 - distance
                    metadata = results["metadatas"][q_idx][m_idx] if results["metadatas"] else {}
                    matches.append((match_id, similarity, metadata))

                    if len(matches) >= n_results:
                        break

            all_results.append(matches)

    return all_results


def get_index_count() -> int:
    """Get the total number of items in the ChromaDB index."""
    collection = get_collection()
    return collection.count()


def reset_collection():
    """Delete and recreate the collection. Use for testing only."""
    global _collection
    client = _get_client()
    try:
        client.delete_collection(name=COLLECTION_NAME)
        logger.warning(f"Deleted ChromaDB collection '{COLLECTION_NAME}'")
    except Exception:
        pass
    _collection = None
    return get_collection()

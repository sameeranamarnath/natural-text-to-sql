"""Qdrant access for schema chunks and worked examples.

The collection holds one point per chunk of DDL / documentation / past query, so
the agent retrieves only the tables and patterns that matter for a question
instead of stuffing the whole schema into the prompt.
"""

from typing import Any

from qdrant_client import QdrantClient, models

from config import get_settings
from llm import embed_model


def client() -> QdrantClient:
    s = get_settings()
    return QdrantClient(url=s.qdrant_url, api_key=s.qdrant_api_key)


def ensure_collection() -> str:
    s = get_settings()
    c = client()
    if not c.collection_exists(s.qdrant_collection):
        c.create_collection(
            collection_name=s.qdrant_collection,
            vectors_config=models.VectorParams(
                size=s.embed_dim, distance=models.Distance.COSINE
            ),
        )
    return s.qdrant_collection


def upsert_chunks(chunks: list[str], metadatas: list[dict[str, Any]]) -> int:
    """Embed and store chunks. Idempotent per call: ids are assigned by index offset."""
    collection = ensure_collection()
    vectors = embed_model().embed_documents(chunks)
    c = client()
    start = c.count(collection_name=collection).count
    points = [
        models.PointStruct(id=start + i, vector=vec, payload={"text": text, **meta})
        for i, (text, vec, meta) in enumerate(zip(chunks, vectors, metadatas))
    ]
    c.upsert(collection_name=collection, points=points)
    return len(points)


def search(query: str, top_k: int | None = None) -> list[dict[str, Any]]:
    s = get_settings()
    collection = ensure_collection()
    vector = embed_model().embed_query(query)
    hits = client().search(
        collection_name=collection,
        query_vector=vector,
        limit=top_k or s.retrieval_top_k,
        with_payload=True,
    )
    return [{"score": h.score, **(h.payload or {})} for h in hits]

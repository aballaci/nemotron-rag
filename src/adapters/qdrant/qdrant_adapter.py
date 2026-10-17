"""Qdrant vector store adapter.

Implements VectorStorePort using Qdrant with payload-based ABAC filtering.
"""

from __future__ import annotations

import uuid
from typing import List

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from core.models import Chunk, RetrievalResult, UserContext
from ports.vector_store_port import VectorStorePort

COLLECTION_NAME = "company_knowledge"
VECTOR_SIZE = 2048  # Nemotron-3-Embed-1B output dimension


class QdrantAdapter(VectorStorePort):
    """Qdrant implementation of VectorStorePort."""

    def __init__(self, host: str = "qdrant", port: int = 6333):
        self.client = QdrantClient(host=host, port=port)

    def create_collection(self) -> None:
        """Ensure the vector collection exists with correct schema."""
        try:
            self.client.get_collection(collection_name=COLLECTION_NAME)
        except Exception:
            self.client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=qmodels.VectorParams(
                    size=VECTOR_SIZE,
                    distance=qmodels.Distance.COSINE,
                ),
            )
            # Create payload indexes for ABAC pre-filtering
            self.client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="confidentiality_level",
                field_type=qmodels.PayloadFieldType.INTEGER,
            )
            self.client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="department",
                field_type=qmodels.PayloadFieldType.KEYWORD,
            )
            self.client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="tenant_id",
                field_type=qmodels.PayloadFieldType.KEYWORD,
            )

    def upsert_chunks(
        self,
        chunks: List[Chunk],
        vectors: List[List[float]],
    ) -> List[str]:
        """Write chunk vectors and metadata to Qdrant."""
        points = []
        for chunk, vector in zip(chunks, vectors):
            # Qdrant requires point ID to be an unsigned int or UUID
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk.chunk_id))
            payload = {
                "chunk_id": chunk.chunk_id,
                "doc_id": chunk.doc_id,
                "text": chunk.text,
                "chunk_index": chunk.chunk_index,
                "confidentiality_level": chunk.confidentiality_level,
                "department": chunk.department,
                "classification": chunk.classification,
                "owner": chunk.owner,
                "tenant_id": chunk.metadata.get("tenant_id", ""),
            }
            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        self.client.upsert(
            collection_name=COLLECTION_NAME,
            points=points,
        )
        return [c.chunk_id for c in chunks]

    def search(
        self,
        query_vector: List[float],
        user_context: UserContext,
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """Search for similar chunks, pre-filtered by user attributes."""
        # ABAC pre-filter via Qdrant payload conditions
        filter_conditions = qmodels.Filter(
            must=[
                qmodels.FieldCondition(
                    key="tenant_id",
                    match=qmodels.MatchValue(value=user_context.tenant_id),
                ),
                qmodels.FieldCondition(
                    key="confidentiality_level",
                    range=qmodels.Range(lte=user_context.clearance_level),
                ),
                qmodels.FieldCondition(
                    key="department",
                    match=qmodels.MatchValue(value=user_context.department),
                ),
            ]
        )

        search_result = self.client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=filter_conditions,
            limit=top_k,
            with_payload=True,
        )

        results: List[RetrievalResult] = []
        for hit in search_result:
            payload = hit.payload or {}
            chunk = Chunk(
                chunk_id=payload.get("chunk_id", ""),
                doc_id=payload.get("doc_id", ""),
                text=payload.get("text", ""),
                confidentiality_level=payload.get("confidentiality_level", 0),
                department=payload.get("department", ""),
                classification=payload.get("classification", ""),
                owner=payload.get("owner", ""),
                chunk_index=payload.get("chunk_index", 0),
                vector_id=str(hit.id),
            )
            results.append(RetrievalResult(chunk=chunk, score=hit.score))

        return results

    def delete_chunks_by_doc(self, doc_id: str) -> int:
        """Delete all chunks for a document. Returns count deleted."""
        result = self.client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="doc_id",
                            match=qmodels.MatchValue(value=doc_id),
                        )
                    ]
                )
            ),
        )
        return result.deleted_count if hasattr(result, "deleted_count") else 0

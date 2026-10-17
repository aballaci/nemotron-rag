"""Background ingestion tasks for the worker.

Entry point for RQ/Celery workers. Decouples slow embedding/indexing
from HTTP request handling.
"""

from __future__ import annotations

from typing import Any, Dict

from adapters.qdrant.qdrant_adapter import QdrantAdapter
from adapters.openrouter.embedding_adapter import OpenRouterEmbeddingAdapter
from application.use_cases.ingest_document import IngestDocumentUseCase
from ports.document_store_port import DocumentStorePort


def ingest_document_task(
    doc_id: str,
    title: str,
    text: str,
    confidentiality_level: int,
    department: str,
    classification: str,
    owner: str,
    tenant_id: str,
    source_path: str,
    openrouter_api_key: str,
    qdrant_host: str = "qdrant",
    qdrant_port: int = 6333,
) -> Dict[str, Any]:
    """Celery/RQ task: ingest a document in the background."""

    embedding_adapter = OpenRouterEmbeddingAdapter(
        api_key=openrouter_api_key,
    )
    vector_store = QdrantAdapter(host=qdrant_host, port=qdrant_port)
    vector_store.create_collection()

    # DocumentStorePort would be injected here; using a placeholder for now
    document_store: DocumentStorePort = None  # type: ignore

    use_case = IngestDocumentUseCase(
        embedding_adapter=embedding_adapter,
        vector_store=vector_store,
        document_store=document_store,
    )

    result = use_case.execute(
        doc_id=doc_id,
        title=title,
        text=text,
        confidentiality_level=confidentiality_level,
        department=department,
        classification=classification,
        owner=owner,
        tenant_id=tenant_id,
        source_path=source_path,
    )

    return {
        "doc_id": result.doc_id,
        "chunks_indexed": result.chunks_indexed,
        "vectors_written": result.vectors_written,
        "status": result.status,
    }

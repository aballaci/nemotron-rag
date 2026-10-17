"""FastAPI routes for the RAG agent.

Routes are thin: parse request → call use case → return response.
Business logic lives in application/use_cases.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from adapters.qdrant.qdrant_adapter import QdrantAdapter
from adapters.openrouter.embedding_adapter import OpenRouterEmbeddingAdapter
from application.use_cases.ingest_document import IngestDocumentUseCase

router = APIRouter()


class IngestRequest(BaseModel):
    doc_id: str
    title: str
    text: str
    confidentiality_level: int  # 1-4
    department: str
    classification: str
    owner: str
    tenant_id: str
    source_path: str


class IngestResponse(BaseModel):
    doc_id: str
    chunks_indexed: int
    vectors_written: int
    status: str


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(request: IngestRequest):
    """Ingest a single document into the RAG knowledge base."""
    try:
        embedding_adapter = OpenRouterEmbeddingAdapter(
            api_key="PLACEHOLDER",  # TODO: inject from settings/env
        )
        vector_store = QdrantAdapter()
        vector_store.create_collection()

        use_case = IngestDocumentUseCase(
            embedding_adapter=embedding_adapter,
            vector_store=vector_store,
            document_store=None,  # TODO: inject MinIO adapter
        )

        result = use_case.execute(
            doc_id=request.doc_id,
            title=request.title,
            text=request.text,
            confidentiality_level=request.confidentiality_level,
            department=request.department,
            classification=request.classification,
            owner=request.owner,
            tenant_id=request.tenant_id,
            source_path=request.source_path,
        )

        return IngestResponse(
            doc_id=result.doc_id,
            chunks_indexed=result.chunks_indexed,
            vectors_written=result.vectors_written,
            status=result.status,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

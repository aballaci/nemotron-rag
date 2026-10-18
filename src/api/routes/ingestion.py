"""FastAPI routes for document ingestion.

Thin route: validate JWT → parse request → call use case → return response.
Business logic lives in application/use_cases/ingest_document.py.

Security:
  - Requires a valid Bearer JWT on the Authorization header (write path).
  - JWT is validated via JWTAdapter, producing the authenticated UserContext.
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from adapters.auth.jwt_adapter import JWTAdapter
from adapters.openrouter.embedding_adapter import OpenRouterEmbeddingAdapter
from adapters.openrouter.settings import load_openrouter_api_key
from adapters.qdrant.qdrant_adapter import QdrantAdapter
from application.use_cases.ingest_document import IngestDocumentUseCase
from core.models import UserContext

router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)

_jwt = JWTAdapter(
    secret=os.getenv("JWT_SECRET", "changeme-please-replace-with-a-strong-secret")
)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> UserContext:
    """Validate the Bearer JWT and return the authenticated UserContext.

    Raises 401 if no token or invalid/expired token.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization: Bearer <token> header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return _jwt.validate_token(credentials.credentials)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )


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
async def ingest_document(
    request: IngestRequest,
    user_context: UserContext = Depends(get_current_user),
):
    """Ingest a single document into the RAG knowledge base."""
    try:
        embedding_adapter = OpenRouterEmbeddingAdapter(
            api_key=load_openrouter_api_key(),
        )
        vector_store = QdrantAdapter()
        vector_store.create_collection()

        use_case = IngestDocumentUseCase(
            embedding_adapter=embedding_adapter,
            vector_store=vector_store,
            document_store=None,
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
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

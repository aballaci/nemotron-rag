"""FastAPI routes for query (ask) endpoint.

Thin route: parse request → validate JWT → call use case → return response.
Business logic lives in application/use_cases/ask_question.py.

Security:
  - Requires a valid Bearer JWT on the Authorization header.
  - JWT is validated via JWTAdapter, producing the UserContext used for ABAC.
  - Every query is written to the PostgreSQL audit log.
"""

from __future__ import annotations

import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from adapters.auth.jwt_adapter import JWTAdapter
from adapters.auth.settings import load_jwt_secret
from adapters.openrouter.chat_adapter import OpenRouterChatAdapter
from adapters.openrouter.settings import load_openrouter_api_key
from adapters.openrouter.embedding_adapter import OpenRouterEmbeddingAdapter
from adapters.postgresql.postgres_adapter import PostgresAdapter
from adapters.qdrant.qdrant_adapter import QdrantAdapter
from application.use_cases.ask_question import AskQuestionUseCase
from core.models import UserContext

router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)

# Module-level adapters (wired once at import time)
_embedding = OpenRouterEmbeddingAdapter(api_key=load_openrouter_api_key())
_vector_store = QdrantAdapter()
_chat = OpenRouterChatAdapter(api_key=load_openrouter_api_key())
_jwt_secret = load_jwt_secret()
_jwt = JWTAdapter(secret=_jwt_secret)
_postgres_dsn = os.getenv(
    "POSTGRES_DSN",
    "postgresql://{user}:{password}@{host}:{port}/{db}".format(
        user=os.getenv("POSTGRES_USER", "rag"),
        password=os.getenv("POSTGRES_PASSWORD", "changeme"),
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        db=os.getenv("POSTGRES_DB", "rag"),
    ),
)
_postgres = PostgresAdapter(dsn=_postgres_dsn)
use_case = AskQuestionUseCase(
    embedding_adapter=_embedding,
    vector_store=_vector_store,
    chat_adapter=_chat,
    postgres_adapter=_postgres,
    top_k=5,
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


class AskRequest(BaseModel):
    question: str
    top_k: int = 5


class SourceCitation(BaseModel):
    chunk_id: str
    doc_id: str
    title: str = ""
    chunk_index: int
    text_snippet: str
    confidentiality_level: int
    department: str
    score: float


class AskResponse(BaseModel):
    answer: str
    sources: List[SourceCitation] = []
    retrieved_chunk_ids: List[str] = []
    model: str
    context_used: bool
    context_tokens_estimate: int | None = None


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    user_context: UserContext = Depends(get_current_user),
):
    """Answer a user question using RAG with ABAC-pre-filtered retrieval.

    The user_context (tenant, department, clearance) is derived from the
    validated JWT and drives ABAC pre-filtering in Qdrant.
    """
    try:
        result = use_case.execute(
            question=request.question,
            user_context=user_context,
        )

        return AskResponse(
            answer=result["answer"],
            sources=[
                SourceCitation(
                    chunk_id=s["chunk_id"],
                    doc_id=s["doc_id"],
                    title=s["title"],
                    chunk_index=s["chunk_index"],
                    text_snippet=s["text_snippet"],
                    confidentiality_level=s["confidentiality_level"],
                    department=s["department"],
                    score=s["score"],
                )
                for s in result["sources"]
            ],
            retrieved_chunk_ids=result["retrieved_chunk_ids"],
            model=result["model"],
            context_used=result["context_used"],
            context_tokens_estimate=result.get("context_tokens_estimate"),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

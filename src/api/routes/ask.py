"""FastAPI routes for query (ask) endpoint.

Thin route: parse request → call use case → return response.
Business logic lives in application/use_cases/ask_question.py.

IMPORTANT (Documentation Handoff):
  JWT authentication is currently a MOCK implementation.
  The /ask endpoint uses a hardcoded UserContext (demo_user, tenant
  t_acme_corp_001, department engineering, clearance_level 2) instead of
  validating a real JWT.

  The JWT adapter (src/adapters/auth/jwt_adapter.py) exists and is unit-tested,
  but it is NOT wired into this route. To enable real auth, replace
  _mock_user_context() with JWT validation:

      token = extract_bearer_token(request.headers.get("Authorization"))
      user_context = jwt_adapter.validate_token(token)

"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from adapters.openrouter.chat_adapter import OpenRouterChatAdapter
from adapters.qdrant.qdrant_adapter import QdrantAdapter
from adapters.openrouter.embedding_adapter import OpenRouterEmbeddingAdapter
from application.use_cases.ask_question import AskQuestionUseCase
from core.models import UserContext

router = APIRouter()


class AskRequest(BaseModel):
    question: str
    top_k: int = 5


class SourceCitation(BaseModel):
    chunk_id: str
    doc_id: str
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


# Module-level singletons (wired once at import time)
_embedding = OpenRouterEmbeddingAdapter(
    api_key="PLACEHOLDER",  # TODO: inject from settings/env
)
_vector_store = QdrantAdapter()
_chat = OpenRouterChatAdapter(
    api_key="PLACEHOLDER",  # TODO: inject from settings/env
)
use_case = AskQuestionUseCase(
    embedding_adapter=_embedding,
    vector_store=_vector_store,
    chat_adapter=_chat,
    postgres_adapter=None,  # Postgres audit logging not yet wired
    top_k=5,
)


def _mock_user_context() -> UserContext:
    """Temporary mock: returns a fixed UserContext instead of validating a JWT.

    REPLACE WITH: token validation via JWTAdapter.validate_token(token)
    """
    return UserContext(
        user_id="demo_user",
        tenant_id="t_acme_corp_001",
        roles=["engineer"],
        department="engineering",
        clearance_level=2,
        location="US",
        employment_status="active",
    )


@router.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    """Answer a user question using RAG with ABAC-pre-filtered retrieval."""
    try:
        user_context = _mock_user_context()

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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

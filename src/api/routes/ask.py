"""FastAPI routes for query (ask) endpoint.

Thin route: parse request → call use case → return response.
Business logic lives in application/use_cases/ask_question.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from adapters.openrouter.chat_adapter import OpenRouterChatAdapter
from adapters.qdrant.qdrant_adapter import QdrantAdapter
from adapters.openrouter.embedding_adapter import OpenRouterEmbeddingAdapter
from application.use_cases.ask_question import AskQuestionUseCase

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


@router.post("/ask", response_model=AskResponse)
async def ask_question(request: AskRequest):
    """Answer a user question using RAG with ABAC-pre-filtered retrieval."""
    try:
        # TODO: Extract UserContext from validated JWT via AuthPort
        # For now, using a default test context.
        # In production, JWT validation happens at the gateway/middleware layer
        # and user attributes are injected here.
        from core.models import UserContext

        user_context = UserContext(
            user_id="demo_user",
            tenant_id="t_acme_corp_001",
            roles=["engineer"],
            department="engineering",
            clearance_level=2,
            location="US",
            employment_status="active",
        )

        embedding_adapter = OpenRouterEmbeddingAdapter(
            api_key="PLACEHOLDER",  # TODO: inject from settings/env
        )
        vector_store = QdrantAdapter()
        chat_adapter = OpenRouterChatAdapter(api_key="PLACEHOLDER")

        use_case = AskQuestionUseCase(
            embedding_adapter=embedding_adapter,
            vector_store=vector_store,
            chat_adapter=chat_adapter,
            top_k=request.top_k,
        )

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

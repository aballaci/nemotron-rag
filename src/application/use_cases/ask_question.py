"""AskQuestion use case.

Orchestrates: question → embed → vector search (ABAC pre-filter) → context build → LLM generate.
Returns answer with source citations.
"""

from __future__ import annotations

from typing import List

from adapters.openrouter.chat_adapter import OpenRouterChatAdapter
from adapters.qdrant.qdrant_adapter import QdrantAdapter
from adapters.openrouter.embedding_adapter import OpenRouterEmbeddingAdapter
from application.services.context_builder import build_context, build_system_prompt
from core.models import UserContext


class AskQuestionUseCase:
    """Use case for answering a user question using RAG."""

    def __init__(
        self,
        embedding_adapter: OpenRouterEmbeddingAdapter,
        vector_store: QdrantAdapter,
        chat_adapter: OpenRouterChatAdapter,
        top_k: int = 5,
    ):
        self.embedding = embedding_adapter
        self.vector_store = vector_store
        self.chat = chat_adapter
        self.top_k = top_k

    def execute(
        self,
        question: str,
        user_context: UserContext,
    ) -> dict:
        """Answer a question using RAG with ABAC-filtered retrieval."""

        # 1. Embed question (input_type: query)
        query_vector = self.embedding.embed_query(question)

        # 2. Retrieve top-K chunks with ABAC pre-filtering
        results = self.vector_store.search(query_vector, user_context, top_k=self.top_k)

        # 3. Build context from retrieved chunks
        context_block = build_context(results, max_tokens=6000)

        if not context_block:
            return {
                "answer": "I could not find any relevant information in the knowledge base for your question.",
                "sources": [],
                "retrieved_chunk_ids": [],
                "model": "nvidia/nemotron-3.5-super-vl",
                "context_used": False,
            }

        # 4. Build system prompt with grounded instructions
        system_prompt = build_system_prompt(context_block)

        # 5. Generate answer via OpenRouter chat
        answer = self.chat.generate_answer(
            system_prompt=system_prompt,
            user_question=question,
            temperature=0.2,
        )

        # 6. Build source citations
        sources = []
        for result in results:
            chunk = result.chunk
            sources.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "doc_id": chunk.doc_id,
                    "chunk_index": chunk.chunk_index,
                    "text_snippet": chunk.text[:200],
                    "confidentiality_level": chunk.confidentiality_level,
                    "department": chunk.department,
                    "score": result.score,
                }
            )

        return {
            "answer": answer,
            "sources": sources,
            "retrieved_chunk_ids": [r.chunk.chunk_id for r in results],
            "model": "nvidia/nemotron-3.5-super-vl",
            "context_used": True,
            "context_tokens_estimate": len(context_block) // 4,
        }

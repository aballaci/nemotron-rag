#!/usr/bin/env python3
"""Test full RAG pipeline end-to-end with ABAC filtering."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from adapters.qdrant.qdrant_adapter import QdrantAdapter
from adapters.openrouter.embedding_adapter import OpenRouterEmbeddingAdapter
from adapters.openrouter.chat_adapter import OpenRouterChatAdapter
from application.use_cases.ask_question import AskQuestionUseCase
from core.models import UserContext


def make_user(user_id: str, tenant_id: str, roles: list, department: str,
              clearance_level: int, location: str = "US",
              employment_status: str = "active") -> UserContext:
    return UserContext(
        user_id=user_id,
        tenant_id=tenant_id,
        roles=roles,
        department=department,
        clearance_level=clearance_level,
        location=location,
        employment_status=employment_status,
    )


def run_rag(use_case: AskQuestionUseCase, question: str, user: UserContext, label: str):
    print("=" * 60)
    print(f"{label}: {question}")
    print("=" * 60)

    result = use_case.execute(question=question, user_context=user)

    print(f"\nAnswer: {result['answer']}")
    print(f"Context used: {result['context_used']}")
    print(f"Retrieved chunks: {[s['doc_id'] for s in result['sources']]}")
    for s in result['sources']:
        print(f"  - {s['doc_id']} (Dept: {s['department']}, Tier: {s['confidentiality_level']}, Score: {s['score']:.4f})")
    print()


def main():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set")
        sys.exit(1)

    embedding = OpenRouterEmbeddingAdapter(api_key=api_key)
    vector_store = QdrantAdapter(host="localhost", port=6333)
    chat = OpenRouterChatAdapter(api_key=api_key)

    use_case = AskQuestionUseCase(
        embedding_adapter=embedding,
        vector_store=vector_store,
        chat_adapter=chat,
        top_k=5,
    )

    alice = make_user(
        user_id="u_alice", tenant_id="t_acme_corp_001",
        roles=["engineer"], department="engineering",
        clearance_level=2,
    )

    marcus = make_user(
        user_id="u_marcus", tenant_id="t_acme_corp_001",
        roles=["manager"], department="engineering",
        clearance_level=3,
    )

    diana = make_user(
        user_id="u_diana", tenant_id="t_acme_corp_001",
        roles=["legal_counsel"], department="legal",
        clearance_level=4,
    )

    stranger = make_user(
        user_id="u_stranger", tenant_id="t_other_company",
        roles=["admin"], department="engineering",
        clearance_level=4,
    )

    # Test 1: Alice (Clearance 2) asks salary — should NOT get Tier 3
    run_rag(use_case, "What are the engineering salary bands?", alice, "Alice (Clearance 2)")

    # Test 2: Marcus (Clearance 3) asks salary — SHOULD get Tier 3
    run_rag(use_case, "What are the engineering salary bands?", marcus, "Marcus (Clearance 3)")

    # Test 3: Diana (Legal, Clearance 4) asks salary — should NOT get Engineering docs
    run_rag(use_case, "What are the engineering salary bands?", diana, "Diana (Legal, Clearance 4)")

    # Test 4: Stranger (Different Tenant) — should get nothing
    run_rag(use_case, "What are the engineering salary bands?", stranger, "Stranger (Different Tenant)")

    # Test 5: Alice asks about public press release — should work
    run_rag(use_case, "What did Acme Corp report in Q3 2024?", alice, "Alice asks public press release")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Exploratory test cases for the Nemotron RAG agent on ace.

Exercises the full pipeline:
  embed_query -> Qdrant ABAC pre-filter -> context build -> OpenRouter chat

Tests cover:
  1. Alice (Engineer, Clearance 2) — salary query (should be DENIED Tier 3)
  2. Marcus (Engineering Manager, Clearance 3) — salary query (should GET Tier 3)
  3. Diana (Legal Counsel, Clearance 4) — cross-department query (should be DENIED Engineering)
  4. Stranger (Different tenant) — any query (should get NOTHING)
  5. Alice (Clearance 2) — public press release (should work, Tier 1)
  6. Diana (Legal, Clearance 4) — M&A restricted query (should GET Tier 4)
  7. Irrelevant query (should gracefully refuse)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from adapters.qdrant.qdrant_adapter import QdrantAdapter
from adapters.openrouter.embedding_adapter import OpenRouterEmbeddingAdapter
from adapters.openrouter.chat_adapter import OpenRouterChatAdapter
from adapters.postgresql.postgres_adapter import PostgresAdapter
from application.use_cases.ask_question import AskQuestionUseCase
from core.models import UserContext


def make_user(user_id: str, name: str, tenant_id: str, roles: list,
              department: str, clearance_level: int,
              location: str = "US", employment_status: str = "active") -> UserContext:
    return UserContext(
        user_id=user_id,
        tenant_id=tenant_id,
        roles=roles,
        department=department,
        clearance_level=clearance_level,
        location=location,
        employment_status=employment_status,
        contractor=False,
    )


def run_case(use_case: AskQuestionUseCase, question: str, user: UserContext,
             label: str, expected_behavior: str):
    """Run a single RAG query and print results."""
    print("=" * 70)
    print(f"TEST: {label}")
    print(f"User: {user.user_id} | {user.department} | Clearance {user.clearance_level}")
    print(f"Question: {question}")
    print(f"Expected: {expected_behavior}")
    print("=" * 70)

    result = use_case.execute(question=question, user_context=user)

    print(f"\nAnswer: {result['answer']}")
    print(f"\nMetadata:")
    print(f"  Context used: {result['context_used']}")
    print(f"  Model: {result['model']}")
    print(f"  Latency: {result.get('latency_ms', 'N/A')} ms")
    print(f"  Retrieved chunks: {len(result['retrieved_chunk_ids'])}")
    for s in result["sources"]:
        print(f"    - {s['doc_id']} (Dept: {s['department']}, Tier: {s['confidentiality_level']}, Score: {s['score']:.4f})")
        print(f"      Snippet: {s['text_snippet'][:80]}...")
    print()


def main():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set")
        sys.exit(1)

    embedding = OpenRouterEmbeddingAdapter(api_key=api_key)
    vector_store = QdrantAdapter(host="localhost", port=6333)
    chat = OpenRouterChatAdapter(api_key=api_key)
    mock_postgres = MagicMock(spec=PostgresAdapter)

    use_case = AskQuestionUseCase(
        embedding_adapter=embedding,
        vector_store=vector_store,
        chat_adapter=chat,
        postgres_adapter=mock_postgres,
        top_k=5,
    )

    # ── User Personas ──
    alice = make_user(
        "u_alice", "Alice Engineer", "t_acme_corp_001",
        ["engineer"], "engineering", clearance_level=2
    )
    marcus = make_user(
        "u_marcus", "Marcus Manager", "t_acme_corp_001",
        ["manager"], "engineering", clearance_level=3
    )
    diana = make_user(
        "u_diana", "Diana Legal", "t_acme_corp_001",
        ["legal_counsel"], "legal", clearance_level=4
    )
    stranger = make_user(
        "u_stranger", "Stranger X", "t_other_company",
        ["admin"], "engineering", clearance_level=4
    )

    # ── Test Cases ──
    run_case(
        use_case,
        "What are the engineering salary bands?",
        alice,
        "Alice (Engineer, Clearance 2) asks salary",
        "DENIED: Clearance 2 < Tier 3 required"
    )

    run_case(
        use_case,
        "What are the engineering salary bands?",
        marcus,
        "Marcus (Manager, Clearance 3) asks salary",
        "GRANTED: Clearance 3 >= Tier 3"
    )

    run_case(
        use_case,
        "What are the engineering salary bands?",
        diana,
        "Diana (Legal, Clearance 4) asks salary",
        "DENIED: Wrong department (legal != engineering)"
    )

    run_case(
        use_case,
        "What are the engineering salary bands?",
        stranger,
        "Stranger (Different Tenant) asks salary",
        "DENIED: Different tenant_id"
    )

    run_case(
        use_case,
        "What did Acme Corp report in Q3 2024?",
        alice,
        "Alice asks public press release",
        "GRANTED: Tier 1 public doc, dept=all"
    )

    run_case(
        use_case,
        "What is Project Alpha about?",
        diana,
        "Diana (Legal) asks M&A question",
        "GRANTED: Legal dept, Clearance 4 >= Tier 4"
    )

    run_case(
        use_case,
        "What is the meaning of life?",
        alice,
        "Alice asks irrelevant question",
        "GRACEFUL REFUSAL: No matching context"
    )


if __name__ == "__main__":
    main()

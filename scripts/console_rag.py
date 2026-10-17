#!/usr/bin/env python3
"""
Console client for the Nemotron RAG agent.

Simulates a person asking questions through the terminal.
Supports switching user personas (clearance, department, tenant) to test
ABAC access control interactively.

Usage:
    cd ~/dev/nemotron-rag
    source .venv/bin/activate
    export OPENROUTER_API_KEY=sk-or-....
    export PYTHONPATH=src
    python scripts/console_rag.py
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


# Pre-defined personas
PERSONAS = {
    "1": UserContext(
        user_id="u_alice",
        tenant_id="t_acme_corp_001",
        roles=["engineer"],
        department="engineering",
        clearance_level=2,
        location="US",
        employment_status="active",
        contractor=False,
    ),
    "2": UserContext(
        user_id="u_marcus",
        tenant_id="t_acme_corp_001",
        roles=["manager"],
        department="engineering",
        clearance_level=3,
        location="US",
        employment_status="active",
        contractor=False,
    ),
    "3": UserContext(
        user_id="u_diana",
        tenant_id="t_acme_corp_001",
        roles=["legal_counsel"],
        department="legal",
        clearance_level=4,
        location="US",
        employment_status="active",
        contractor=False,
    ),
    "4": UserContext(
        user_id="u_stranger",
        tenant_id="t_other_company",
        roles=["admin"],
        department="engineering",
        clearance_level=4,
        location="US",
        employment_status="active",
        contractor=False,
    ),
    "5": UserContext(
        user_id="u_bob",
        tenant_id="t_acme_corp_001",
        roles=["intern"],
        department="hr",
        clearance_level=1,
        location="US",
        employment_status="inactive",
        contractor=False,
    ),
}


def build_use_case() -> AskQuestionUseCase:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set in environment")
        print("  export OPENROUTER_API_KEY=sk-or-....")
        raise SystemExit(1)

    embedding = OpenRouterEmbeddingAdapter(api_key=api_key)
    vector_store = QdrantAdapter(host="localhost", port=6333)
    chat = OpenRouterChatAdapter(api_key=api_key)
    mock_postgres = MagicMock(spec=PostgresAdapter)

    return AskQuestionUseCase(
        embedding_adapter=embedding,
        vector_store=vector_store,
        chat_adapter=chat,
        postgres_adapter=mock_postgres,
        top_k=5,
    )


def print_personas() -> None:
    print("\nAvailable personas:")
    for key, ctx in PERSONAS.items():
        status = "ACTIVE" if ctx.employment_status == "active" else "INACTIVE"
        print(f"  {key}. {ctx.user_id} | {ctx.department} | Clearance {ctx.clearance_level} | {status}")
    print()


def choose_persona(current: UserContext) -> UserContext:
    print_personas()
    choice = input(f"Select persona [1-5] (current: {current.user_id}): ").strip()
    if choice in PERSONAS:
        return PERSONAS[choice]
    print(f"Keeping current persona: {current.user_id}")
    return current


def print_result(label: str, result: dict) -> None:
    print(f"\n{'=' * 60}")
    print(f"ANSWER ({label}):")
    print(f"{'=' * 60}")
    print(result["answer"])
    print(f"\n--- Metadata ---")
    print(f"Context used: {result['context_used']}")
    print(f"Model: {result['model']}")
    print(f"Latency: {result.get('latency_ms', 'N/A')} ms")
    print(f"Retrieved chunks: {len(result['retrieved_chunk_ids'])}")
    for s in result["sources"]:
        print(
            f"  - {s['doc_id']}#{s['chunk_index']} "
            f"(Dept: {s['department']}, Tier: {s['confidentiality_level']}, "
            f"Score: {s['score']:.4f})"
        )
        print(f"      {s['text_snippet'][:100]}...")
    print()


def main() -> None:
    use_case = build_use_case()
    user = PERSONAS["1"]  # default: Alice

    print("=" * 60)
    print("Nemotron RAG Agent — Console Client")
    print("=" * 60)
    print("Commands:")
    print("  /persona  - Switch user persona")
    print("  /whoami   - Show current user")
    print("  /help     - Show this help")
    print("  /quit     - Exit")
    print("  <question> - Ask a question")
    print("=" * 60)

    print(f"\nCurrent user: {user.user_id} | {user.department} | Clearance {user.clearance_level}")

    while True:
        try:
            line = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not line:
            continue

        if line == "/quit" or line == "/exit":
            print("Goodbye!")
            break

        if line == "/help":
            print("Commands: /persona, /whoami, /help, /quit")
            continue

        if line == "/whoami":
            print(f"User: {user.user_id}")
            print(f"Tenant: {user.tenant_id}")
            print(f"Department: {user.department}")
            print(f"Roles: {', '.join(user.roles)}")
            print(f"Clearance: {user.clearance_level}")
            print(f"Employment: {user.employment_status}")
            continue

        if line == "/persona":
            user = choose_persona(user)
            print(f"Switched to: {user.user_id} | {user.department} | Clearance {user.clearance_level}")
            continue

        # Treat as a question
        result = use_case.execute(question=line, user_context=user)
        print_result(user.user_id, result)


if __name__ == "__main__":
    main()

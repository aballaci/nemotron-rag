"""Unit tests for RAG agent ABAC security and context building.

Pure unit tests — no Docker, no OpenRouter, no network required.
Mocks QdrantAdapter.search() to verify ABAC pre-filtering behavior.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from core.models import Chunk, RetrievalResult, UserContext
from adapters.qdrant.qdrant_adapter import (
    ACTIVE_EMPLOYMENT_STATUS,
    ALL_DEPARTMENTS,
    QdrantAdapter,
)
from adapters.openrouter.embedding_adapter import OpenRouterEmbeddingAdapter
from adapters.openrouter.chat_adapter import OpenRouterChatAdapter
from application.use_cases.ask_question import AskQuestionUseCase
from adapters.postgresql.postgres_adapter import PostgresAdapter
from application.services.context_builder import build_context


# ---------------------------------------------------------------------------
# Fake (mock) QdrantAdapter for deterministic unit testing
# ---------------------------------------------------------------------------
class FakeQdrantAdapter(QdrantAdapter):
    """In-memory replacement for QdrantAdapter.search() used in unit tests."""

    def __init__(self, chunks: List[Chunk]):
        self._chunks = chunks

    def create_collection(self) -> None:
        pass

    def upsert_chunks(self, chunks: List[Chunk], vectors: List[List[float]]) -> List[str]:
        return [c.chunk_id for c in chunks]

    def search(
        self,
        query_vector: List[float],
        user_context: UserContext,
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """Simulate Qdrant ABAC pre-filtering."""
        results = []
        for chunk in self._chunks:
            # ABAC rules: tenant match + department match + clearance check
            if chunk.metadata.get("tenant_id") != user_context.tenant_id:
                continue
            if chunk.department not in (user_context.department, ALL_DEPARTMENTS):
                continue
            if chunk.confidentiality_level > user_context.clearance_level:
                continue
            if user_context.employment_status != ACTIVE_EMPLOYMENT_STATUS:
                continue
            results.append(
                RetrievalResult(chunk=chunk, score=0.9 - len(results) * 0.1)
            )
            if len(results) >= top_k:
                break
        return results

    def delete_chunks_by_doc(self, doc_id: str) -> int:
        return 0


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------
def make_chunk(doc_id: str, text: str, tier: int, department: str,
               chunk_index: int = 0, tenant_id: str = "t_acme_corp_001") -> Chunk:
    return Chunk(
        chunk_id=f"{doc_id}#{chunk_index}",
        doc_id=doc_id,
        text=text,
        confidentiality_level=tier,
        department=department,
        classification="test",
        owner="test_owner",
        chunk_index=chunk_index,
        metadata={"tenant_id": tenant_id},
    )


def make_user(user_id: str, tenant_id: str, roles: list[str], department: str,
              clearance_level: int, employment_status: str = "active") -> UserContext:
    return UserContext(
        user_id=user_id,
        tenant_id=tenant_id,
        roles=roles,
        department=department,
        clearance_level=clearance_level,
        location="US",
        employment_status=employment_status,
        contractor=False,
    )


# ---------------------------------------------------------------------------
# Test documents (12 synthetic docs matching our dataset)
# ---------------------------------------------------------------------------
CHUNKS = [
    make_chunk("doc-001", "Company press release Q3 2024 results", 1, "all", 0),
    make_chunk("doc-002", "Employee onboarding guide", 1, "all", 0),
    make_chunk("doc-003", "Engineering org chart", 2, "engineering", 0),
    make_chunk("doc-004", "IT security policy", 2, "it", 0),
    make_chunk("doc-005", "Engineering salary bands confidential", 3, "engineering", 0),
    make_chunk("doc-006", "Product roadmap Q1-Q2 2025", 3, "product", 0),
    make_chunk("doc-007", "HR handbook leave policy", 3, "hr", 0),
    make_chunk("doc-008", "M&A Project Alpha target analysis", 4, "legal", 0),
    make_chunk("doc-009", "Executive compensation review", 4, "executive", 0),
    make_chunk("doc-010", "Legal investigation vendor billing", 4, "legal", 0),
    make_chunk("doc-011", "HR investigation workplace complaint", 4, "hr", 0),
    make_chunk("doc-012", "IT incident data breach attempt", 4, "it", 0),
]
CHUNKS_BY_ID = {c.chunk_id: c for c in CHUNKS}


def retrieved_chunks(result: dict) -> List[Chunk]:
    """Chunks the use case retrieved (ABAC-filtered), independent of citations."""
    return [CHUNKS_BY_ID[chunk_id] for chunk_id in result["retrieved_chunk_ids"]]


def make_use_case(chunks: List[Chunk] = CHUNKS) -> AskQuestionUseCase:
    fake_vector_store = FakeQdrantAdapter(chunks)
    embedding_adapter = MagicMock(spec=OpenRouterEmbeddingAdapter)
    chat_adapter = MagicMock(spec=OpenRouterChatAdapter)
    chat_adapter.generate_answer.return_value = "Mocked answer"

    fake_postgres = MagicMock(spec=PostgresAdapter)

    return AskQuestionUseCase(
        embedding_adapter=embedding_adapter,
        vector_store=fake_vector_store,
        chat_adapter=chat_adapter,
        postgres_adapter=fake_postgres,
        top_k=5,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_alice_clearance_2_cannot_see_tier_3():
    """Alice (Engineering, Clearance 2) asks about salary bands.
    Must NOT retrieve Tier 3 doc-005 (salary bands)."""
    uc = make_use_case()
    user = make_user("u_alice", "t_acme_corp_001", ["engineer"], "engineering", 2)
    result = uc.execute(question="What are the engineering salary bands?", user_context=user)

    retrieved_tiers = {c.confidentiality_level for c in retrieved_chunks(result)}
    assert 3 not in retrieved_tiers, "Alice (Clearance 2) must NOT see Tier 3 salary data"
    assert 4 not in retrieved_tiers, "Alice (Clearance 2) must NOT see Tier 4 data"
    print("PASS: Alice (Clearance 2) cannot see Tier 3/4 documents")


def test_marcus_clearance_3_can_see_tier_3():
    """Marcus (Engineering Manager, Clearance 3) asks about salary bands.
    SHOULD retrieve Tier 3 doc-005."""
    uc = make_use_case()
    user = make_user("u_marcus", "t_acme_corp_001", ["manager"], "engineering", 3)
    result = uc.execute(question="What are the engineering salary bands?", user_context=user)

    doc_ids = {c.doc_id for c in retrieved_chunks(result)}
    assert "doc-005" in doc_ids, "Marcus (Clearance 3) must see Tier 3 salary doc-005"
    print("PASS: Marcus (Clearance 3) can see Tier 3 document")


def test_diana_legal_cannot_see_engineering():
    """Diana (Legal, Clearance 4) asks about salary bands.
    Must NOT retrieve any Engineering department docs despite high clearance."""
    uc = make_use_case()
    user = make_user("u_diana", "t_acme_corp_001", ["legal_counsel"], "legal", 4)
    result = uc.execute(question="What are the engineering salary bands?", user_context=user)

    departments = {c.department for c in retrieved_chunks(result)}
    assert "engineering" not in departments, "Diana (Legal) must not see Engineering docs"
    print("PASS: Diana (Legal, Clearance 4) cannot see Engineering documents")


def test_stranger_different_tenant_gets_nothing():
    """Stranger from different tenant asks about salary bands.
    Must retrieve 0 chunks due to tenant_id mismatch."""
    uc = make_use_case()
    user = make_user("u_stranger", "t_other_company", ["admin"], "engineering", 4)
    result = uc.execute(question="What are the engineering salary bands?", user_context=user)

    assert result["retrieved_chunk_ids"] == [], "Different tenant must retrieve 0 chunks"
    assert result["context_used"] is False
    print("PASS: Stranger from different tenant gets nothing")


def test_inactive_user_gets_nothing():
    """User with employment_status=inactive retrieves nothing."""
    uc = make_use_case()
    user = make_user("u_fired", "t_acme_corp_001", ["engineer"], "engineering", 4,
                     employment_status="inactive")
    result = uc.execute(question="What are the salary bands?", user_context=user)

    assert result["retrieved_chunk_ids"] == [], "Inactive user must retrieve 0 chunks"
    assert result["context_used"] is False
    print("PASS: Inactive user gets nothing")


def test_engineer_can_see_company_wide_press_release():
    uc = make_use_case()
    user = make_user("u_alice", "t_acme_corp_001", ["engineer"], "engineering", 1)
    result = uc.execute(question="What was Q3 2024 revenue?", user_context=user)

    assert "doc-001#0" in result["retrieved_chunk_ids"]


def test_qdrant_search_department_filter_includes_all():
    adapter = QdrantAdapter.__new__(QdrantAdapter)
    adapter.client = MagicMock()
    adapter.client.query_points.return_value.points = []
    user = make_user("u_alice", "t_acme_corp_001", ["engineer"], "engineering", 2)

    adapter.search([0.0], user)

    query_filter = adapter.client.query_points.call_args.kwargs["query_filter"]
    department = next(c for c in query_filter.must if c.key == "department")
    assert department.match.any == ["engineering", ALL_DEPARTMENTS]


def test_qdrant_search_inactive_user_gets_nothing_without_querying():
    adapter = QdrantAdapter.__new__(QdrantAdapter)
    adapter.client = MagicMock()
    user = make_user("u_bob", "t_acme_corp_001", ["intern"], "hr", 1,
                     employment_status="inactive")

    results = adapter.search([0.0], user)

    assert results == []
    adapter.client.query_points.assert_not_called()


def test_context_builder_truncates_to_token_budget():
    """Context builder must not exceed max_tokens."""
    chunks = [
        make_chunk(f"doc-{i:03d}", "x" * 1000, 2, "engineering", i) for i in range(10)
    ]
    results = [RetrievalResult(chunk=c, score=0.9) for c in chunks]
    context = build_context(results, max_tokens=500)

    # Each chunk is ~1000 chars = ~250 tokens, so 500 token budget = ~2 chunks
    tokens = len(context) // 4
    assert tokens <= 500, f"Context exceeded token budget: {tokens} tokens"
    print(f"PASS: Context builder truncated to {tokens} tokens (budget: 500)")


def test_jwt_adapter_generates_valid_token():
    """JWT adapter generates and validates tokens correctly."""
    from adapters.auth.jwt_adapter import JWTAdapter

    adapter = JWTAdapter(secret="test-secret")
    token = adapter.generate_test_token(
        user_id="u_test",
        tenant_id="t_test",
        roles=["engineer"],
        department="engineering",
        clearance_level=3,
    )
    ctx = adapter.validate_token(token)
    assert ctx.user_id == "u_test"
    assert ctx.tenant_id == "t_test"
    assert ctx.clearance_level == 3
    assert ctx.department == "engineering"
    print("PASS: JWT adapter generates and validates tokens")


if __name__ == "__main__":
    test_alice_clearance_2_cannot_see_tier_3()
    test_marcus_clearance_3_can_see_tier_3()
    test_diana_legal_cannot_see_engineering()
    test_stranger_different_tenant_gets_nothing()
    test_inactive_user_gets_nothing()
    test_context_builder_truncates_to_token_budget()
    test_jwt_adapter_generates_valid_token()
    print("\nAll unit tests passed!")


# ---------------------------------------------------------------------------
# Auth requirement tests
# ---------------------------------------------------------------------------
def test_ask_route_requires_valid_jwt():
    """The /ask route must reject requests without a valid Bearer JWT."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routes import ask as ask_module

    # Build a minimal app so TestClient has proper middleware stack.
    app = FastAPI()
    app.include_router(ask_module.router, prefix="/api/v1")
    client = TestClient(app)

    # No Authorization header -> 401
    resp = client.post("/api/v1/ask", json={"question": "hi"})
    assert resp.status_code == 401, f"expected 401, got {resp.status_code}: {resp.text}"

    # Invalid token -> 401
    resp = client.post(
        "/api/v1/ask",
        json={"question": "hi"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert resp.status_code == 401, f"expected 401, got {resp.status_code}: {resp.text}"

    # Valid token -> proceeds past auth (may fail later on OpenRouter, but not 401)
    # Route's JWTAdapter uses JWT_SECRET env (default insecure value).
    # Generate the token with the same secret so signature verification passes.
    adapter = ask_module.JWTAdapter(
        secret="changeme-please-replace-with-a-strong-secret"
    )
    token = adapter.generate_test_token(
        user_id="u_test", tenant_id="t_test", roles=["engineer"],
        department="engineering", clearance_level=2,
    )
    resp = client.post(
        "/api/v1/ask",
        json={"question": "hi"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code != 401, f"valid token should not be 401: {resp.status_code} {resp.text}"

    print("PASS: /ask requires a valid Bearer JWT")


def test_ingest_route_requires_valid_jwt():
    """The /ingest route must reject requests without a valid Bearer JWT."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from api.routes import ingestion as ingest_module

    app = FastAPI()
    app.include_router(ingest_module.router, prefix="/api/v1")
    client = TestClient(app)

    # No Authorization header -> 401
    resp = client.post(
        "/api/v1/ingest",
        json={"doc_id": "d1", "title": "t", "text": "x", "confidentiality_level": 1,
              "department": "eng", "classification": "c", "owner": "o",
              "tenant_id": "t1", "source_path": "s"},
    )
    assert resp.status_code == 401, f"expected 401, got {resp.status_code}: {resp.text}"

    # Invalid token -> 401
    resp = client.post(
        "/api/v1/ingest",
        json={"doc_id": "d1", "title": "t", "text": "x", "confidentiality_level": 1,
              "department": "eng", "classification": "c", "owner": "o",
              "tenant_id": "t1", "source_path": "s"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert resp.status_code == 401, f"expected 401, got {resp.status_code}: {resp.text}"

    print("PASS: /ingest requires a valid Bearer JWT")


if __name__ == "__main__":
    test_alice_clearance_2_cannot_see_tier_3()
    test_marcus_clearance_3_can_see_tier_3()
    test_diana_legal_cannot_see_engineering()
    test_stranger_different_tenant_gets_nothing()
    test_inactive_user_gets_nothing()
    test_context_builder_truncates_to_token_budget()
    test_jwt_adapter_generates_valid_token()
    test_ask_route_requires_valid_jwt()
    test_ingest_route_requires_valid_jwt()
    print("\nAll unit tests passed!")

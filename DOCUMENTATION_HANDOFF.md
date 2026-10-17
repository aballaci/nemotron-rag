# Documentation Handoff — Nemotron RAG Agent

**Project:** Enterprise Multi-Tenant ABAC RAG Agent  
**Phase:** 5 (Documentation Handoff)  
**Status:** Complete — ready for operator handoff  
**Location:** `~/dev/nemotron-rag/` (code), `~/Documents/docs/nemotron-rag/` (spec kit + architecture)

---

## 1. Which Part Does What

| Directory/File | Role | What it does |
|----------------|------|--------------|
| `docker-compose.yml` | Infrastructure orchestration | Starts PostgreSQL, Qdrant, Redis on `ace` via Docker Compose. Internal network, no host ports except Qdrant 127.0.0.1:6333. |
| `migrations/001_initial_schema.sql` | Database schema | Creates `documents`, `chunks`, `audit_log` tables on PostgreSQL first start. |
| `src/core/models.py` | Domain layer | Pure Python dataclasses: `Chunk`, `Document`, `UserContext`, `RetrievalResult`. Zero framework imports. |
| `src/ports/` | Interface contracts | Abstract base classes: `EmbeddingPort`, `VectorStorePort`, `ChatModelPort`, `AuthPort`, `DocumentStorePort`. Hexagonal architecture boundary. |
| `src/adapters/openrouter/embedding_adapter.py` | Infrastructure | Calls OpenRouter `/embeddings` with `nvidia/nemotron-3-embed-1b:free`. `input_type: "passage"` for docs, `"query"` for search. |
| `src/adapters/openrouter/chat_adapter.py` | Infrastructure | Calls OpenRouter `/chat/completions` with `nvidia/nemotron-3.5-super-vl`. Generates grounded answers from context. |
| `src/adapters/qdrant/qdrant_adapter.py` | Infrastructure | Qdrant vector store. Creates collection (2048-dim, cosine). Upserts chunk vectors with ABAC payload metadata. Searches with pre-filter: `tenant_id`, `department`, `confidentiality_level <= clearance_level`. |
| `src/adapters/auth/jwt_adapter.py` | Infrastructure | Validates OIDC JWTs via PyJWT. Extracts `user_id`, `tenant_id`, `roles`, `department`, `clearance_level`, `employment_status`. Includes `generate_test_token()` for dev. |
| `src/adapters/postgresql/postgres_adapter.py` | Infrastructure | Inserts document records, chunk metadata, and audit log entries into PostgreSQL. |
| `src/application/use_cases/ingest_document.py` | Use case | Orchestrates ingestion: chunk → embed → index → persist metadata. ABAC-tagged at index time. |
| `src/application/use_cases/ask_question.py` | Use case | Orchestrates query: embed question → ABAC pre-filtered Qdrant search → context build → LLM generate → audit log. |
| `src/application/services/context_builder.py` | Service | Merges retrieved chunks, truncates to token budget (~6000), injects source citations, builds grounded system prompt. |
| `src/api/routes/ask.py` | Interface layer | FastAPI `/ask` endpoint. Thin wrapper around `AskQuestionUseCase`. |
| `src/api/routes/ingestion.py` | Interface layer | FastAPI `/ingest` endpoint. Thin wrapper around `IngestDocumentUseCase`. |
| `src/main.py` | Interface layer | FastAPI app factory. Registers `/api/v1/ingest` and `/api/v1/ask`. |
| `src/worker/tasks.py` | Background jobs | Celery/RQ task entrypoint for background ingestion (not yet wired). |
| `scripts/generate_test_data.py` | Dev tool | Generates 12 synthetic multi-tier documents (Public/Internal/Confidential/Restricted) across 7 departments. |
| `scripts/ingest_dataset.py` | Dev tool | Runs the ingestion pipeline against the generated dataset. |
| `scripts/explore_rag.py` | Dev tool | Exploratory end-to-end test with 7 user personas and ABAC scenarios. |
| `src/tests/test_abac_security.py` | Unit tests | 7 tests: clearance gates, department isolation, tenant isolation, inactive user, token budget, JWT generation. All pass. |
| `spec-kit/` | Governance | ADRs, policies, schemas, contracts, runbooks, change management. See `spec-kit/index.md`. |
| `docs/` | Project docs | `README.md`, `ENTERPRISE_ARCHITECTURE.md` (mirrored to Obsidian vault). |

---

## 2. What Is the Role of Each Major Component

### API Gateway (`/api/v1/ask`, `/api/v1/ingest`)
Single entry point for all client requests. Thin — no business logic. Parses Pydantic request, calls use case, returns Pydantic response.

### Ingestion Use Case (`src/application/use_cases/ingest_document.py`)
The **write path** of CQRS. Receives raw document text, chunks it (~512 tokens, 50 overlap), embeds with OpenRouter `input_type: "passage"`, writes vectors + ABAC metadata to Qdrant, persists metadata to PostgreSQL.

### Query Use Case (`src/application/use_cases/ask_question.py`)
The **read path** of CQRS. Receives user question + `UserContext`, embeds with `input_type: "query"`, searches Qdrant with ABAC pre-filter, builds context from results, generates answer via OpenRouter chat, logs to audit trail.

### Context Builder (`src/application/services/context_builder.py`)
Sorts retrieved chunks by score, truncates to fit ~6000 token budget, formats with `[doc-id#chunk-index]` citations, builds system prompt that instructs the LLM to answer only from context.

### Qdrant Adapter
Vector store with payload-based ABAC. Every chunk stored with `tenant_id`, `department`, `confidentiality_level`. Every search pre-filters: tenant must match, department must match, `confidentiality_level <= user.clearance_level`.

### JWT Adapter
Validates signed JWTs, extracts subject attributes. Includes `generate_test_token()` for development. Unit-tested but **not yet wired into the FastAPI route** (see Section 5).

---

## 3. Why Is It Needed (Design Rationale)

| Decision | Why |
|----------|-----|
| **OpenRouter only, no local LLMs** | `ace` has no GPU. Avoids CUDA driver management, model downloads, VRAM constraints. Model swaps are config changes, not infrastructure changes. |
| **ABAC over ACL** | ACL requires re-indexing every chunk when a user leaves (Bob problem). ABAC deactivates the IdP account — instant revocation, zero re-indexing. |
| **Hexagonal (Ports & Adapters)** | Business logic (agent loop, security filter) never imports Qdrant, OpenRouter, or FastAPI directly. Swap any adapter without touching core logic. |
| **CQRS** | Ingestion (slow, background, write-heavy) and querying (synchronous, read-heavy, security-critical) scale and fail differently. |
| **ReAct agent loop** | The LLM decides whether to retrieve, how many times, and whether results are sufficient before answering. |
| **Docker Compose on ace** | Explicit service boundaries, reproducible images, internal network isolation. Single `docker compose up -d` brings up the full stack. |
| **Spec Kit governance** | ADRs, contracts, policies, and runbooks gate every phase. No code without an approved artifact. |

---

## 4. Alternatives Considered (and Rejected)

| Decision | Alternative | Reason Rejected |
|----------|-------------|-----------------|
| OpenRouter API | Local vLLM/Ollama on ace | No GPU on ace; would require CUDA drivers and 24GB+ VRAM for Nemotron-3.5-Super-VL |
| ABAC | ACL user-lists on chunks | Re-indexing on every permission change; doesn't scale to enterprise org churn |
| Docker Compose | Kubernetes/k3s | Overkill for a single Linux box; high operational complexity |
| Qdrant | pgvector | Qdrant has native payload filtering and purpose-built vector search; pgvector would work but is less purpose-built |
| Python | Java/Go | Python has the mature LLM/RAG ecosystem (LangChain-adjacent patterns, OpenAI SDK compatibility). Java/Go would require more hand-rolled glue code. |
| MinIO object store | Direct file storage | MinIO (S3-compatible) was planned but blocked on ace Docker Hub. Replaced with direct text ingestion for MVP; object store can be added later. |

---

## 5. JWT Authentication — Current Status (Intentional Mock)

**The `/ask` endpoint uses a MOCK JWT implementation.**

**Current behavior:** `src/api/routes/ask.py` calls `_mock_user_context()` which returns a hardcoded `UserContext`:
- `user_id`: `demo_user`
- `tenant_id`: `t_acme_corp_001`
- `department`: `engineering`
- `clearance_level`: 2
- `employment_status`: `active`

**What exists but is NOT wired:**
- `src/adapters/auth/jwt_adapter.py` — full JWTAdapter with `validate_token()` and `generate_test_token()`. Unit-tested (7 tests pass).
- The adapter is ready to drop in: replace `_mock_user_context()` with `jwt_adapter.validate_token(token)` extracted from the `Authorization: Bearer <token>` header.

**Why it's a mock:** JWT identity provider (Keycloak/Authentik/OIDC) setup was deferred to keep Phase 1–3 focused on the core RAG loop and ABAC enforcement. The ABAC logic itself is fully tested and working — only the JWT→UserContext wiring remains.

**To enable real auth:**
```python
# In src/api/routes/ask.py, replace _mock_user_context() with:
token = request.headers.get("Authorization", "").replace("Bearer ", "")
user_context = jwt_adapter.validate_token(token)
```

---

## 6. Next Steps — Intentionally Left for Later

These items were **deliberately deferred** to keep the initial delivery focused. They are tracked in `spec-kit/process/change-management.md` and require a new ADR before implementation.

| # | Item | Why Deferred | How to Implement |
|---|------|--------------|------------------|
| 1 | **Real JWT auth** | Identity provider (Keycloak/Authentik) not yet deployed on ace | Wire `JWTAdapter.validate_token()` into `/ask` route; deploy IdP container |
| 2 | **PostgreSQL audit logging** | `PostgresAdapter` exists but isn't called from `ask_question.py` | Inject `PostgresAdapter` into `AskQuestionUseCase`; call `log_audit()` on every query |
| 3 | **MinIO document store** | Blocked on ace Docker Hub (`minio/minio` image unavailable) | Add MinIO container when image access is resolved; wire `DocumentStorePort` |
| 4 | **Observability** | Structured logging, metrics, dashboards deferred | Add JSON logging, Prometheus metrics, Grafana; trace query latency and token counts |
| 5 | **Multi-tenancy enforcement at gateway** | Tenant ID in JWT but not enforced at API Gateway level | Add Traefik middleware to extract and forward `tenant_id`; rate-limit per tenant |
| 6 | **Conversation memory** | Stateless per-request design chosen intentionally | Add session store (Redis) and conversation history to context builder |
| 7 | **Document upload UI** | API-first; no frontend built | Add file upload endpoint that writes to MinIO and triggers ingestion worker |
| 8 | **Re-indexing on ACL change** | Documented in spec-kit but not automated | When a document's `confidentiality_level` changes, delete old vectors and re-embed |

---

## 7. How to Run on ace

```bash
cd ~/dev/nemotron-rag

# 1. Configure environment
cp .env.example .env
chmod 600 .env
# Edit .env: set OPENROUTER_API_KEY

# 2. Docker secrets
echo -n "your-postgres-password" > secrets/postgres_password.txt
chmod 600 secrets/*.txt

# 3. Start infrastructure
docker compose up -d
docker compose ps

# 4. Run exploratory tests
source .venv/bin/activate
export PYTHONPATH=src
export OPENROUTER_API_KEY=sk-or-...
python3 scripts/explore_rag.py

# 5. Run unit tests
python3 -m pytest src/tests/test_abac_security.py -v
```

---

## 8. Spec Kit Inventory (Governance)

| Artifact | Path | Status |
|----------|------|--------|
| ADR 0001 | `spec-kit/adr/0001-use-openrouter.md` | Accepted |
| ADR 0002 | `spec-kit/adr/0002-use-abac-over-acl.md` | Accepted |
| ADR 0003 | `spec-kit/adr/0003-docker-compose-on-ace.md` | Accepted |
| Classification policy | `spec-kit/policy/classification.md` | Approved |
| ABAC policy (Rego) | `spec-kit/policy/abac.rego` | Approved |
| Chunk metadata schema | `spec-kit/schema/chunk-metadata.json` | Approved |
| Audit log schema | `spec-kit/schema/audit-log.json` | Approved |
| Query API contract | `spec-kit/contracts/query-api.yaml` | Approved |
| Definition of Done | `spec-kit/process/dod.md` | Approved |
| Change management | `spec-kit/process/change-management.md` | Approved |
| Offboarding runbook | `spec-kit/runbooks/offboarding.md` | Approved |

All mirrored to Obsidian vault at `~/Documents/docs/nemotron-rag/spec-kit/`.

---

## 9. Verification Summary

**Verified on `ace` (live, real OpenRouter calls):**

| Test | Result |
|------|--------|
| Alice (Clearance 2) — salary query | DENIED Tier 3, got Tier 2 only |
| Marcus (Clearance 3) — salary query | GRANTED Tier 3 with citation `[doc-005#0]` |
| Diana (Legal, Clearance 4) — salary query | DENIED wrong department |
| Stranger (Different tenant) — salary query | DENIED, 0 chunks |
| Alice — public press release | GRANTED Tier 1 |
| Diana — M&A restricted query | GRANTED Tier 4 with citation `[doc-008#0]` |
| Alice — irrelevant question | Graceful refusal |
| 7 unit tests | All pass |

**Not yet verified (deferred):**
- Real JWT authentication (mock in place)
- PostgreSQL audit log writes (adapter exists, not wired)
- MinIO object storage (image blocked on ace Docker Hub)
- Observability/metrics
- Multi-tenant gateway rate limiting

---

**Document Control:** Version 1.0 | Owner: Architecture | Review: On next ADR or major change

# Nemotron RAG Agent

A multi-tier hybrid Retrieval-Augmented Generation (RAG) agent built on a single Linux host (`ace`). It answers natural-language questions against a private company knowledge base using NVIDIA models hosted on OpenRouter, with attribute-based access control (ABAC) to prevent permission leakage.

---

## Scope

### What it does
- Ingests documents (PDF, Markdown, text) into a vector store with chunk-level metadata.
- Embeds documents and user queries via OpenRouter (`nvidia/nemotron-3-embed-1b`).
- Retrieves relevant context using hybrid semantic + keyword search, pre-filtered by user attributes.
- Generates grounded answers via OpenRouter (`nvidia/nemotron-3.5-super-vl`) using only retrieved context.
- Enforces confidentiality tiers (`public`, `internal`, `confidential`, `restricted`) at retrieval time so users never see unauthorized documents.
- Logs every query and retrieved chunk for auditability.

### What it does not do
- No local model inference (no GPUs, no CUDA, no local Transformers serving).
- No ACL user-lists stored on chunks (access is attribute- and policy-based).
- No chat history or multi-turn conversation memory (stateless per request).
- No built-in UI (API-first; console/client integration is external).

---

## Architecture

### Design patterns
- **CQRS** — separate write path (ingestion: chunk → embed → index) and read path (query: embed → search → answer).
- **Hexagonal (Ports & Adapters)** — business logic (agent loop, security filter) depends on interfaces, not on Qdrant, OpenRouter, or FastAPI directly.
- **ReAct agent loop** — the LLM decides whether to retrieve, how many times, and whether results are sufficient before answering.
- **ABAC (Attribute-Based Access Control)** — access decisions evaluate subject attributes (from JWT) against resource attributes (on chunks), not static user lists.

### Components

| Component | Responsibility | Location |
|-----------|---------------|----------|
| Traefik / Nginx | TLS termination, routing, rate limiting | Public entry |
| Keycloak / Authentik / OIDC stub | Authentication, issues JWT with subject attributes | Internal |
| FastAPI Orchestrator | API surface, agent loop, context building | Internal (`api` container) |
| Ingestion Worker | Chunking, embedding, indexing (background) | Internal (`worker` container) |
| PostgreSQL | Document metadata, chunk ACL attributes, audit log | Internal |
| Qdrant | Vector store with payload filtering (cosine similarity, 2048-dim) | Internal |
| MinIO | Raw document object store (pre-chunking) | Internal |
| Redis | Job queue / event bus for ingestion | Internal |
| OpenRouter | Embedding and chat model inference | External API (`https://openrouter.ai/api/v1`) |

### Data flow (query)

```
User question
    │
    ▼
JWT validation (roles, department, clearance_level)
    │
    ▼
Embed question (OpenRouter, input_type="query")
    │
    ▼
Vector search (Qdrant) + keyword search (PostgreSQL)
    │  PRE-FILTER: confidentiality_level <= user.clearance_level
    │            department == user.department
    │            employment_status == "active"
    ▼
Retrieve top-K authorized chunks
    │
    ▼
Context builder (merge, dedupe, truncate, citations)
    │
    ▼
OpenRouter chat (nvidia/nemotron-3.5-super-vl)
    │
    ▼
Answer + source citations
```

Only **text** is sent to OpenRouter. Embedding vectors remain inside Qdrant on `ace`.

---

## Security model

Permission leakage is prevented by enforcing access **at the retrieval layer**, before any text reaches the LLM.

- **ABAC, not ACL:** Chunks carry resource attributes (`confidentiality_level`, `department`, `classification`, `owner`). Users carry subject attributes in their JWT (`department`, `clearance_level`, `employment_status`).
- **Policy:** `allow if user.clearance_level >= resource.confidentiality_level AND user.department == resource.department AND user.employment_status == "active"`.
- **Instant offboarding:** When a user leaves, deactivating their IdP account revokes access immediately — no re-indexing of chunks required.
- **No post-filtering:** Unauthorized chunks never reach the context builder or the LLM.

---

## Technology stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.14 |
| Web framework | FastAPI |
| Background jobs | Redis + RQ / Celery |
| Vector store | Qdrant |
| Metadata store | PostgreSQL (Row-Level Security) |
| Object store | MinIO (S3-compatible) |
| Embeddings | OpenRouter → `nvidia/nemotron-3-embed-1b:free` |
| Chat | OpenRouter → `nvidia/nemotron-3.5-super-vl` |
| Container orchestration | Docker Compose |
| Identity | OIDC / Keycloak (or stub) |

---

## Key architectural decisions

Recorded in `spec-kit/adr/`:

- **ADR 0001:** OpenRouter for all model inference (no local LLMs).
- **ADR 0002:** ABAC over ACL for document access.
- **ADR 0003:** Docker Compose on `ace` for infrastructure orchestration.

---

## Project structure

```
nemotron-rag/
├── docker-compose.yml          # Infrastructure (Postgres, Qdrant, MinIO, Redis)
├── .env.example                # Environment template
├── .gitignore                  # Excludes .env, secrets, .venv
├── retrieval_test.py           # Verified OpenRouter RAG script (POC)
├── migrations/
│   └── 001_initial_schema.sql  # documents, chunks, audit_log tables
├── secrets/                    # Docker secret files (gitignored)
├── spec-kit/                   # Governance (ADRs, contracts, policies, runbooks)
│   ├── adr/
│   ├── contracts/
│   ├── policy/
│   ├── process/
│   ├── runbooks/
│   └── schema/
├── src/                        # Application source (modular monolith)
│   ├── core/                   # Domain models
│   ├── ports/                  # Interface contracts
│   ├── application/            # Use cases, agent loop, security filter
│   ├── adapters/               # OpenRouter, Qdrant, Postgres, MinIO
│   ├── api/                    # FastAPI routes
│   ├── worker/                 # Ingestion tasks
│   ├── config.py
│   ├── container.py
│   └── main.py
├── tests/                      # Unit + integration tests
└── docker/                     # Dockerfiles
```

Documentation and governance mirrors live in the Obsidian vault at `~/Documents/docs/nemotron-rag/`.

---

## Getting started

```bash
cd ~/dev/nemotron-rag

cp .env.example .env
chmod 600 .env
# Edit .env: set OPENROUTER_API_KEY

echo -n "your-postgres-password" > secrets/postgres_password.txt
echo -n "your-minio-password"   > secrets/minio_password.txt
chmod 600 secrets/*.txt

docker compose up -d
docker compose ps
```

Once the storage plane is healthy, proceed to Phase 1 (ingestion pipeline) and Phase 2 (query agent) as outlined in `spec-kit/process/dod.md`.

---

## Roadmap

1. **Phase 0:** Foundations + Spec Kit (Docker, secrets, ADRs) — complete
2. **Phase 1:** Storage & Ingestion Plane (schema, Qdrant collection, embedding worker)
3. **Phase 2:** Query Plane & MVP Agent (FastAPI `/ask`, ReAct loop, retrieval tools)
4. **Phase 3:** Test Data & Population (multi-tier documents, negative security tests)
5. **Phase 4:** Hardening & Test (unit tests, observability, audit verification)
6. **Phase 5:** Documentation Handoff (operator runbook, spec kit v1.0)

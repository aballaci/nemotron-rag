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
- Provides a Streamlit chat + ingestion UI on port 8501.
- Logs every query and retrieved chunk for auditability (not yet wired; see Known limitations).

### What it does not do
- No local model inference (no GPUs, no CUDA, no local Transformers serving).
- No ACL user-lists stored on chunks (access is attribute- and policy-based).
- No chat history or multi-turn conversation memory (stateless per request).
- Authentication via Bearer JWT on `/api/v1/ask` and `/api/v1/ingest`.

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
| Streamlit UI | Chat + ingestion frontend | `ui` container, port 8501 |
| FastAPI Orchestrator | API surface, agent loop, context building | Internal (`api` container) |
| Ingestion Worker | Chunking, embedding, indexing (background) | Internal (`worker` container) |
| PostgreSQL | Document metadata, chunk ACL attributes, audit log | Internal |
| Qdrant | Vector store with payload filtering (cosine similarity, 2048-dim) | Internal |
| Silo (`pgsty/silo`, MinIO-compatible) | Raw document object store (pre-chunking) | Internal |
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
| Object store | Silo (MinIO-compatible) |
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
├── docker-compose.yml          # Postgres, Qdrant, Redis, Silo, API, UI
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
│   ├── ui/                     # Streamlit app (app.py)
│   ├── api/                    # FastAPI routes
│   ├── worker/                 # Ingestion tasks
│   ├── config.py
│   ├── container.py
│   └── main.py
├── tests/                      # Unit + integration tests
└── docker/                     # Dockerfile.api, Dockerfile.ui
```

Documentation and governance mirrors live in the Obsidian vault at `~/Documents/docs/nemotron-rag/`.

---

## Getting started

```bash
cd ~/dev/nemotron-rag

cp .env.example .env
chmod 600 .env

# Docker secrets (one file per secret, no trailing newline)
echo -n "your-openrouter-key"   > secrets/openrouter_api_key.txt
echo -n "your-postgres-password" > secrets/postgres_password.txt
echo -n "your-jwt-secret"       > secrets/jwt_secret.txt
echo -n "your-silo-password"    > secrets/silo_password.txt
chmod 600 secrets/*.txt

docker compose up -d --build
docker compose ps
```

### Endpoints

| Service | URL | Notes |
|---------|-----|-------|
| Streamlit UI | `http://<host>:8501` | Published on `0.0.0.0:8501`. Reaching it from outside the LAN also needs a router port-forward and a firewall rule for 8501. |
| API | internal only (`http://api:8000`) | Not published to the host. The UI reaches it over the `rag-internal` network. |
| Qdrant | `127.0.0.1:6333` | Localhost only. |

To call the API from the host, use `docker exec rag-api python -c ...` or temporarily add a `127.0.0.1:8000:8000` port mapping to the `api` service.

### Secrets handling

- `secrets/*.txt` and `.env` are gitignored. Only `.env.example` and `secrets/README.md` are tracked.
- The API reads the OpenRouter key from the file named by `OPENROUTER_API_KEY_FILE` (set in `docker-compose.yml`, mounted from `secrets/openrouter_api_key.txt`). See `src/adapters/openrouter/settings.py`.
- Never put a real key in source, compose environment values, or `.env.example`.

### Troubleshooting

- **UI not reachable:** `ui` waits for a healthy `api`. Check `docker compose ps -a` and `docker logs rag-api`; a crashing API leaves `ui` in `Created`.
- **`/ask` returns 500:** the route returns `str(exc)` as the error detail and logs nothing. Reproduce with `docker exec rag-api python -c` against `http://localhost:8000/api/v1/ask` to see the detail. A `401` from OpenRouter means the key file is missing or invalid.
- **Dependency errors in the API container:** `docker/Dockerfile.api` installs from `requirements.txt`; add new packages there and rebuild with `docker compose build api`.

---

## Authentication

Both `/api/v1/ask` and `/api/v1/ingest` require a Bearer JWT:

```bash
curl -X POST http://localhost:8000/api/v1/ask   -H "Authorization: Bearer <jwt>"   -H "Content-Type: application/json"   -d '{"question": "What are the engineering salary bands?"}'
```

The JWT must carry these subject attributes (used for ABAC pre-filtering):
- `sub` — user id
- `tenant_id` — tenant (must match chunk tenant)
- `department` — user department (must match chunk department)
- `clearance_level` — numeric clearance (must be >= resource tier)
- `employment_status` — must be `"active"`

Generate a dev token with the JWT adapter:

```bash
export PYTHONPATH=src
python3 -c "
from adapters.auth.jwt_adapter import JWTAdapter
a = JWTAdapter(secret='changeme-please-replace-with-a-strong-secret')
print(a.generate_test_token(
    user_id='u_alice', tenant_id='t_acme_corp_001',
    roles=['engineer'], department='engineering', clearance_level=2,
))
"
```

Set `JWT_SECRET` in `.env` before any shared deployment (the default is intentionally insecure).

## Known limitations

- `rag-silo` crash-loops (the container prints its help text instead of starting). The API does not depend on it, but raw-document storage is unavailable until the command is fixed.
- The Qdrant healthcheck uses `$line`, which Compose tries to interpolate (warning: `"line" variable is not set`). Escape it as `$$line`.
- Local `secrets/*.txt` files may still contain placeholder values (e.g. `changeme`); replace them before any shared deployment.

---

## Roadmap

1. **Phase 0:** Foundations + Spec Kit (Docker, secrets, ADRs) — complete
2. **Phase 1:** Storage & Ingestion Plane (schema, Qdrant collection, embedding worker)
3. **Phase 2:** Query Plane & MVP Agent (FastAPI `/ask`, ReAct loop, retrieval tools)
4. **Phase 3:** Test Data & Population (multi-tier documents, negative security tests)
5. **Phase 4:** Hardening & Test (unit tests, observability, audit verification)
6. **Phase 5:** Documentation Handoff (operator runbook, spec kit v1.0)

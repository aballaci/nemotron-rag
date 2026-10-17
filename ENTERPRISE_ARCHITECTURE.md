# Enterprise RAG — Multi-Tenant ABAC Architecture

**Project:** Nemotron RAG Agent  
**Target:** Enterprise-grade, multi-tenant, attribute-based access control  
**Deployment:** Single Linux host (`ace`), extensible to multi-node  
**Inference:** OpenRouter (no local LLMs)  
**Governance:** Spec Kit (policy-as-code, ADRs, contracts, runbooks)

---

## 1. Executive Summary

This document describes an enterprise-grade Retrieval-Augmented Generation (RAG) platform designed for **multi-tenant isolation** and **attribute-based access control (ABAC)**. It serves multiple business units, departments, or customers from a single deployment while guaranteeing that no tenant can access another tenant's data, and no user can access documents beyond their assigned attributes.

The system runs on `ace` (a single Linux box) using Docker Compose, with all model inference offloaded to OpenRouter (`nvidia/nemotron-3-embed-1b` for embeddings, `nvidia/nemotron-3.5-super-vl` for chat). Governance is enforced through a **Spec Kit** — a version-controlled set of Architecture Decision Records (ADRs), API contracts, ABAC policies, runbooks, and schemas that gate every implementation phase.

---

## 2. Architecture Overview

### 2.1 Design Principles

| Principle | Enterprise Rationale |
|-----------|---------------------|
| **Tenant Isolation** | Each tenant's data, vectors, and objects are logically isolated. Cross-tenant leakage is prevented at ingestion, retrieval, and audit layers. |
| **ABAC-First Security** | Access decisions evaluate subject attributes (JWT) against resource attributes (chunk metadata), never static user lists. Enables instant offboarding without re-indexing. |
| **CQRS** | Write path (ingestion) and read path (query) are separate services with independent scaling, failure, and security profiles. |
| **Control Plane / Data Plane Split** | Control plane manages tenants, policies, and ingestion scheduling. Data plane executes vector search and LLM generation per tenant context. |
| **Spec Kit Governance** | No code is written without a corresponding approved artifact (ADR, contract, policy, schema). |

### 2.2 High-Level Component Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                     External Clients / Users                        │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ HTTPS + JWT (with tenant_id + attributes)
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    API Gateway (Traefik / Nginx)                    │
│  • TLS termination • Tenant resolution • Rate limiting per tenant   │
│  • JWT validation • WAF • Request routing                           │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ Internal (Docker network)
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Control Plane                                   │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐   │
│  │ Tenant Mgmt │  │ Policy Mgmt  │  │ Ingestion Scheduler     │   │
│  │ (CRUD)      │  │ (OPA/ABAC)   │  │ (Queue + Worker)        │   │
│  └─────────────┘  └──────────────┘  └─────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Data Plane                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    RAG Orchestrator (FastAPI)               │   │
│  │  • ReAct agent loop • Context builder • ABAC pre-filter     │   │
│  │  • Tenant-scoped retrieval • Citation injection             │   │
│  └─────────────────────────────────────────────────────────────┘   │
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
   ┌──────────┐      ┌──────────┐      ┌──────────┐
   │  Qdrant  │      │ PostgreSQL │      │  MinIO   │
   │ (Vectors │      │ (Metadata  │      │ (Objects │
   │  + ABAC  │      │  + RLS)    │      │  raw     │
   │  filter) │      │            │      │  docs)   │
   └──────────┘      └──────────┘      └──────────┘
                           │
                           ▼
                    OpenRouter API
              (Embeddings + Chat)
```

---

## 3. Multitenancy Model

### 3.1 Tenant Definition

A **tenant** is an isolated logical entity (business unit, department, or customer) with:

- A unique `tenant_id` (UUID)
- A dedicated MinIO bucket prefix (`tenant-{tenant_id}/`)
- Isolated vector namespace (shared Qdrant collection with strict `tenant_id` payload filter)
- Isolated PostgreSQL rows (Row-Level Security on `tenant_id`)
- Independent rate limits and quota
- Independent audit log stream

### 3.2 Isolation Layers

| Layer | Mechanism | Enforcement Point |
|-------|-----------|-------------------|
| **Network** | Internal Docker network; no public ports on data services | Gateway → API only |
| **Object Storage** | MinIO bucket prefix per tenant | Ingestion worker |
| **Vector Store** | Qdrant payload filter: `tenant_id == X` | Every search request |
| **Metadata DB** | PostgreSQL RLS policy on `tenant_id` | Every SQL query |
| **Audit Log** | `tenant_id` column; append-only | Orchestrator |
| **Compute** | Per-tenant rate limiting | API Gateway |
| **Encryption** | Optional per-tenant encryption keys (BYOK) | Application layer |

### 3.3 Tenant Context Propagation

Every request carries tenant context through the JWT:

```json
{
  "sub": "u_555",
  "tenant_id": "t_acme_corp",
  "roles": ["engineer"],
  "department": "engineering",
  "clearance_level": 2,
  "employment_status": "active"
}
```

The API Gateway extracts `tenant_id` and injects it into downstream service calls. Services never infer tenant from domain or path alone.

---

## 4. ABAC Security Model

### 4.1 Attribute Taxonomy

| Category | Attribute | Source | Example |
|----------|-----------|--------|---------|
| **Subject** | `user_id` | JWT | `u_555` |
| | `tenant_id` | JWT | `t_acme_corp` |
| | `department` | JWT | `engineering` |
| | `clearance_level` | JWT | `2` |
| | `employment_status` | JWT | `active` |
| | `contractor` | JWT | `false` |
| **Resource** | `confidentiality_level` | Chunk metadata | `3` |
| | `department` | Chunk metadata | `engineering` |
| | `classification` | Chunk metadata | `roadmap` |
| | `owner` | Chunk metadata | `eng_dept` |
| | `tenant_id` | Chunk metadata | `t_acme_corp` |
| **Environment** | `time_of_day` | System | `09:00–18:00` |
| | `network_zone` | Gateway | `internal` |
| | `device_trusted` | Gateway | `true` |

### 4.2 Policy Language (OPA/Rego)

```rego
package rag.authz

default allow = false

allow if {
    # Subject must be active in the same tenant
    input.user.employment_status == "active"
    input.user.tenant_id == input.resource.tenant_id
    
    # Clearance must meet or exceed resource classification
    input.user.clearance_level >= input.resource.confidentiality_level
    
    # Departmental alignment (cross-department access denied by default)
    input.user.department == input.resource.department
    
    # Action must be read
    input.action == "read"
}

deny if {
    not allow
}

deny if {
    input.user.employment_status != "active"
    msg := sprintf("User %s is not active", [input.user.user_id])
}
```

### 4.3 Why ABAC Over ACL (Enterprise Rationale)

| Scenario | ACL (User Lists) | ABAC (Attributes) |
|----------|------------------|-------------------|
| Employee leaves | Re-index every chunk they could read | Deactivate IdP account; instant revocation |
| Department restructure | Update thousands of chunk ACLs | Update user attributes in IdP |
| Temporary contractor | Add to per-chunk lists | Set `contractor=true`, policy denies |
| Cross-tenant access | Impossible to enforce cleanly | `tenant_id` mismatch denies automatically |
| Time-bound access | Not supported | `time_of_day` constraint in policy |

---

## 5. Spec Kit Governance Framework

The Spec Kit is the project's constitution. It contains version-controlled artifacts that must be approved **before** implementation begins.

### 5.1 Artifact Inventory

| Folder | Artifacts | Purpose |
|--------|-----------|---------|
| `adr/` | `0001-openrouter.md`, `0002-abac-over-acl.md`, `0003-docker-compose.md`, `0004-multitenancy.md` | Architecture decisions with rationale |
| `contracts/` | `query-api.yaml`, `ingestion-api.yaml`, `tenant-api.yaml` | OpenAPI contracts between services |
| `policy/` | `classification.md`, `abac.rego` | Data tiers and machine-enforceable access policies |
| `process/` | `dod.md`, `change-management.md` | Definition of Done, change approval workflow |
| `runbooks/` | `offboarding.md`, `tenant-onboarding.md`, `incident-response.md` | Operational procedures |
| `schema/` | `chunk-metadata.json`, `audit-log.json`, `tenant-schema.json` | JSON schemas for data contracts |

### 5.2 Governance Workflow

```
Proposal → Draft ADR → Review → Accept → Implement → Verify (DoD) → Deprecate/Replace
```

No implementation begins until the ADR is `Accepted`. Deviations require a new ADR.

---

## 6. Component Architecture (Detailed)

### 6.1 API Gateway (Control Entry)

- **Tenant Resolution:** Extracts `tenant_id` from JWT or `X-Tenant-ID` header.
- **Rate Limiting:** Per-tenant token bucket (configurable per plan).
- **WAF:** SQL injection, path traversal, payload size limits.
- **TLS:** Mutual TLS optional for internal service communication.

### 6.2 RAG Orchestrator (Data Plane)

Stateless FastAPI service implementing the ReAct loop:

1. **Intent Classification:** Determine if retrieval is needed.
2. **Tool Selection:** Choose `semantic_search`, `keyword_search`, or `refuse`.
3. **Pre-Filter:** Apply ABAC filter derived from JWT (`tenant_id`, `clearance_level`, `department`).
4. **Context Build:** Merge, deduplicate, truncate to token budget, attach citations.
5. **LLM Call:** OpenRouter chat with context + question.
6. **Audit:** Write to `audit_log` with `tenant_id`, `query_hash`, `retrieved_chunk_ids`.

### 6.3 Ingestion Worker (Background)

Consumes events from Redis:

1. **Fetch:** Pull raw document from MinIO (`tenant-{id}/` prefix).
2. **Chunk:** Split into overlapping passages (~512 tokens).
3. **Tag:** Attach `tenant_id`, `confidentiality_level`, `department`, `classification`, `owner`.
4. **Embed:** Call OpenRouter `/embeddings` (`input_type: "passage"`).
5. **Index:** Write vector to Qdrant with payload; write metadata to PostgreSQL.
6. **Audit:** Log ingestion event.

### 6.4 Data Stores

| Store | Tenant Isolation | Technology |
|-------|-----------------|------------|
| Qdrant | `tenant_id` payload filter on every query | `company_knowledge` collection |
| PostgreSQL | Row-Level Security (RLS) on `tenant_id` | `documents`, `chunks`, `audit_log` |
| MinIO | Bucket prefix `tenant-{tenant_id}/` | Object storage |
| Redis | Separate queues or key prefixes per tenant | Job queue |

---

## 7. Data Flows

### 7.1 Ingestion Flow (Multi-Tenant)

```
Document Upload (Tenant A)
    │
    ▼
MinIO: tenant-a/uploads/proposal.pdf
    │
    ▼
Redis event: ingest.{tenant_id}.{doc_id}
    │
    ▼
Ingestion Worker (tenant-aware)
    │
    ├─► Chunk document
    ├─► Tag: tenant_id=t_a, confidentiality_level=3, department=legal
    ├─► OpenRouter embeddings (input_type="passage")
    ├─► Qdrant: upsert vector + payload
    ├─► PostgreSQL: insert chunk row (RLS: tenant_id=t_a)
    └─► Audit log: ingestion event
```

### 7.2 Query Flow (Multi-Tenant)

```
User (Tenant A, Engineer) asks: "What is the Q3 roadmap?"
    │
    ▼
API Gateway: resolve tenant_id=t_a, apply rate limit
    │
    ▼
Orchestrator: validate JWT, extract attributes
    │
    ▼
Embed question (OpenRouter, input_type="query")
    │
    ▼
Qdrant search: WHERE tenant_id='t_a' AND confidentiality_level <= 2
                AND department='engineering'
    │
    ▼
PostgreSQL FTS: WHERE tenant_id='t_a'
    │
    ▼
Context Builder: merge, dedupe, truncate
    │
    ▼
OpenRouter chat: context + question
    │
    ▼
Answer + citations + audit log entry
```

---

## 8. Infrastructure & Deployment

### 8.1 Host Requirements (`ace`)

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 4 cores | 8+ cores |
| RAM | 8 GB | 16+ GB |
| Disk | 100 GB SSD | 500 GB NVMe |
| Network | 1 Gbps | 10 Gbps |
| GPU | Not required | Not required (OpenRouter API) |

### 8.2 Docker Compose Services

| Service | Image | Tenant-Aware | Persistent |
|---------|-------|--------------|------------|
| `postgres` | `postgres:15-alpine` | Yes (RLS) | Yes (volume) |
| `qdrant` | `qdrant/qdrant:latest` | Yes (payload filter) | Yes (volume) |
| `minio` | `minio/minio:latest` | Yes (bucket prefix) | Yes (volume) |
| `redis` | `redis:7-alpine` | Yes (key prefix) | Yes (volume) |
| `api` | Custom (FastAPI) | Yes | No (stateless) |
| `worker` | Custom (Python) | Yes | No (stateless) |

### 8.3 Network Topology

- **External:** HTTPS only to API Gateway (port 443).
- **Internal:** Docker bridge network `rag-internal` (`internal: true`). No container has direct internet access.
- **Outbound:** Only the host (via API orchestrator) reaches OpenRouter API.

---

## 9. Security & Compliance

### 9.1 Security Controls

| Control | Implementation |
|---------|---------------|
| Authentication | OIDC (Keycloak/Authentik) with JWT |
| Authorization | ABAC via OPA/Rego + pre-filter |
| Encryption at rest | Docker volume encryption + application-layer field encryption |
| Encryption in transit | TLS 1.2+ (gateway to clients), internal mTLS optional |
| Secrets | Docker secrets or HashiCorp Vault |
| Audit | Append-only `audit_log` with tenant_id |
| Input validation | Pydantic schemas, OpenAPI contracts |
| Rate limiting | Per-tenant, per-endpoint |

### 9.2 Compliance Mapping

| Requirement | Implementation |
|-------------|---------------|
| GDPR / Right to erasure | Delete document → cascade delete chunks → delete vectors |
| SOC 2 | Audit logs, access reviews, change management (ADRs) |
| HIPAA (if PHI) | Field encryption, BAAs with OpenRouter (if applicable), strict ABAC |
| ISO 27001 | Asset classification (tiers), access control (ABAC), incident response (runbooks) |

---

## 10. Observability & SRE

### 10.1 Metrics

| Metric | Source | Alert Threshold |
|--------|--------|-----------------|
| Query latency (p95) | Orchestrator | > 2s |
| Embedding latency | Worker | > 5s |
| Retrieval refusal rate | Orchestrator | > 5% |
| Tenant query volume | Gateway | Quota breach |
| Failed ingestions | Worker | > 1% |
| Qdrant memory | Qdrant exporter | > 80% |

### 10.2 Logging

- Structured JSON logs to Loki/ELK or local files.
- Every log entry includes `tenant_id`, `user_id`, `request_id`.
- Audit log in PostgreSQL is the source of truth for compliance.

### 10.3 Health Checks

- Each Docker container has a `HEALTHCHECK`.
- Orchestrator exposes `/health` and `/ready` endpoints.
- Circuit breaker on OpenRouter API calls.

---

## 11. Implementation Roadmap

| Phase | Focus | Spec Kit Gate |
|-------|-------|---------------|
| **0** | Foundations + Spec Kit | ADRs 0001–0004 accepted; secrets configured |
| **1** | Storage & Ingestion Plane | `classification.md`, `chunk-metadata.json`, `dod.md` |
| **2** | Query Plane & MVP Agent | `query-api.yaml`, `abac.rego`, negative security tests |
| **3** | Multi-Tenancy | Tenant schema, RLS policies, MinIO bucket isolation |
| **4** | Hardening & Test | Audit log verification, observability, DR drill |
| **5** | Documentation Handoff | Spec kit v1.0 frozen; operator runbook |

---

## 12. Spec Kit Artifact Inventory (Current)

| Path | Status |
|------|--------|
| `spec-kit/adr/0001-use-openrouter.md` | Accepted |
| `spec-kit/adr/0002-use-abac-over-acl.md` | Accepted |
| `spec-kit/adr/0003-docker-compose-on-ace.md` | Accepted |
| `spec-kit/adr/0004-multitenancy.md` | Draft (to be written) |
| `spec-kit/policy/classification.md` | Approved |
| `spec-kit/policy/abac.rego` | Approved |
| `spec-kit/schema/chunk-metadata.json` | Approved |
| `spec-kit/schema/audit-log.json` | Approved |
| `spec-kit/contracts/query-api.yaml` | Approved |
| `spec-kit/process/dod.md` | Approved |
| `spec-kit/process/change-management.md` | Approved |
| `spec-kit/runbooks/offboarding.md` | Approved |

---

## 13. Immediate Next Step

On `ace`:

```bash
cd ~/dev/nemotron-rag

# 1. Configure environment
cp .env.example .env
chmod 600 .env
# Edit .env: OPENROUTER_API_KEY=sk-or-...

# 2. Create Docker secrets
echo -n "your-postgres-password" > secrets/postgres_password.txt
echo -n "your-minio-password"   > secrets/minio_password.txt
chmod 600 secrets/*.txt

# 3. Start infrastructure (Phase 0/1 storage plane)
docker compose up -d

# 4. Verify
docker compose ps
docker compose exec qdrant curl -s localhost:6333/health
```

Once the storage plane is healthy, proceed to Phase 1 implementation: Qdrant collection creation, OpenRouter embedding adapter, and the ingestion worker.

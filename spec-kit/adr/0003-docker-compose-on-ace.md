# ADR 0003: Use Docker Compose on ace for Infrastructure Orchestration

## Status

Accepted

## Context

The RAG agent on `ace` needs to run several infrastructure services:

- PostgreSQL (metadata + RLS)
- Qdrant (vector store with payload filtering)
- MinIO (raw document object store)
- Redis (job queue / event bus for ingestion)

Options considered:

| Option | Pros | Cons |
|--------|------|------|
| **Docker Compose on `ace`** | Explicit service boundaries, reproducible images, internal Docker network, easy teardown/rebuild, standard tooling | Slight learning curve for Compose/YAML, container overhead |
| **Bare metal + systemd** | No container overhead, direct host access | Dependency conflicts (Python versions, `transformers` vs `numpy`), harder to isolate services, manual log rotation, upgrades risk breaking co-located services |
| **Kubernetes / k3s** | Scalable, self-healing | Overkill for a single Linux box, high operational complexity, steep learning curve |
| **Nix / Guix** | Reproducible, declarative | New toolchain to learn, smaller community, fewer pre-built images for Qdrant/MinIO |

## Decision

Use **Docker Compose** on `ace` to orchestrate all infrastructure services.

- All services (`postgres`, `qdrant`, `minio`, `redis`) run in containers on an internal Docker network (`rag-internal`, marked `internal: true`).
- No service ports are published to the host; containers reach each other by service name over the internal network.
- The only outbound internet traffic from `ace` is to OpenRouter (`https://openrouter.ai/api/v1`).
- Secrets are passed via Docker secrets (`secrets/*.txt`), not plaintext environment variables.
- Named Docker volumes persist data across container restarts.

## Consequences

### Positive
- Service boundaries are explicit and versioned via `docker-compose.yml`.
- Rebuilding the environment on another machine is a single `docker compose up`.
- Qdrant, PostgreSQL, MinIO, and Redis are isolated from the public internet.
- Easy to stop/start individual services without affecting the host OS.

### Negative
- Containers add a small overhead compared to bare metal processes.
- Docker must be installed and running on `ace`.
- Debugging requires `docker compose logs` rather than `journalctl` or direct file inspection.

### Mitigations
- Healthchecks are defined for every service so orchestration knows when they are ready.
- A `.env.example` template documents all required configuration.
- The orchestrator (`api`) and ingestion `worker` are also containerized or run from the same codebase, sharing the internal network.

## Related Decisions

- **ADR 0001**: OpenRouter for model inference — no GPU needed on `ace`, so Docker containers remain lightweight (no CUDA toolkit required).
- **ADR 0002**: ABAC over ACL — the PostgreSQL + Qdrant schema supports attribute-based filtering, enforced by the application layer.

# Definition of Done

## Phase 0: Foundations + Spec Kit Init
- [ ] Docker + Docker Compose installed on `ace`
- [ ] `docker-compose.yml` runs `postgres`, `qdrant`, `minio`, `redis` on internal network
- [ ] `OPENROUTER_API_KEY` stored in Docker secrets or restricted `.env`
- [ ] ADRs 0001–0003 accepted in `spec-kit/adr/`
- [ ] Secrets directory gitignored

## Phase 1: Storage & Ingestion Plane
- [ ] `spec-kit/policy/classification.md` approved
- [ ] `spec-kit/schema/chunk-metadata.json` approved
- [ ] Every chunk written to Qdrant carries all `chunk-metadata.json` fields
- [ ] Ingestion worker logs `doc_id`, `user_id`, `confidentiality_level` to audit table
- [ ] Negative test: engineer cannot retrieve Tier 3 HR chunk
- [ ] `spec-kit/process/dod.md` updated for Phase 1

## Phase 2: Query Plane & MVP Agent
- [ ] `spec-kit/contracts/query-api.yaml` approved
- [ ] Every retrieval call pre-filters Qdrant/PostgreSQL using JWT-derived `department` and `clearance_level`
- [ ] Agent returns explicit refusal when no authorized context exists
- [ ] Audit log records `user_id`, `query_hash`, `retrieved_chunk_ids`, `model`, `latency_ms`
- [ ] `spec-kit/process/dod.md` updated for Phase 2

## Phase 3: Test Data & Population
- [ ] Representative documents exist for all 4 tiers
- [ ] Negative test fixtures attached to spec kit
- [ ] `spec-kit/runbooks/offboarding.md` exercised (Bob leaves scenario)
- [ ] `spec-kit/process/dod.md` updated for Phase 3

## Phase 4: Hardening & Test
- [ ] Unit tests for `security_filter.py` pass without Docker/OpenRouter
- [ ] Observability: structured logs, query latency metrics, refusal rate
- [ ] Audit log spot-check: sample query traceable end-to-end
- [ ] `spec-kit/process/dod.md` updated for Phase 4

## Phase 5: Documentation Handoff
- [ ] Spec kit v1.0 frozen (all ADRs, contracts, policies approved)
- [ ] Operator runbook written
- [ ] Retirement criteria defined

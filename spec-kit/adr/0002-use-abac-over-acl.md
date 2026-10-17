# ADR 0002: Use ABAC (Attribute-Based Access Control) Over ACL for Document Access

## Status

Accepted

## Context

The RAG agent must prevent permission leakage: a user must never receive an answer built from document chunks they are not authorized to see.

Options considered:

| Option | Mechanism | Revocation Cost (user leaves) | Expressiveness |
|--------|-----------|-------------------------------|----------------|
| **ACL** (Access Control List) | Each chunk stores `allowed_user_ids` / `allowed_roles`; query filters by list membership | **High**: must find and re-index every chunk the user could read | Low (static lists) |
| **ABAC** (Attribute-Based Access Control) | Chunks carry resource attributes (`confidentiality_level`, `department`, `classification`); users carry subject attributes in JWT; policy evaluates `allow`/`deny` | **Low**: deactivate user in IdP; no re-indexing | High (time, location, department, clearance, employment status) |

## Decision

Use **ABAC** as the access control model.

- Chunks are indexed with resource attributes, not user lists:
  - `confidentiality_level` (numeric: 1=public, 2=internal, 3=confidential, 4=restricted)
  - `department`, `classification`, `owner`
- Users present a JWT containing subject attributes:
  - `department`, `clearance_level`, `location`, `employment_status`, `contractor`
- Retrieval pre-filters Qdrant/PostgreSQL using a policy derived from the JWT:
  ```
  allow if user.clearance_level >= resource.confidentiality_level
  AND user.department == resource.department
  AND user.employment_status == "active"
  ```
- No `allowed_user_ids` or `allowed_roles` fields are stored on chunks.

## Consequences

### Positive
- **Instant offboarding**: when Bob leaves, his IdP account is deactivated; his attributes disappear from the JWT; every future query fails his policy check. **No chunks are re-indexed.**
- Rule changes (e.g., block contractors) require a policy update, not a re-embedding job.
- Scales to enterprise org structures without payload explosion on chunks.

### Negative
- Requires an identity provider that emits rich JWT attributes (Keycloak, Authentik, or OIDC stub).
- Slightly more complex query-time policy evaluation than a simple `IN` list.
- If the IdP is unavailable, retrieval cannot proceed.

### Mitigations
- Phase 1 starts with a lightweight OIDC stub if Keycloak is too heavy.
- Policy logic lives in `src/application/services/security_filter.py`, swapable for OPA later.

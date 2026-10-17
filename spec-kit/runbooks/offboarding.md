# Offboarding Runbook — Bob Leaves the Company

## Scenario
Bob (`u_205`, role: `engineer`, department: `engineering`, clearance_level: 2) leaves the company.

## Goal
Bob must lose access to all company knowledge base documents immediately, with **zero re-indexing**.

## Procedure

### 1. Deactivate Identity
- Disable Bob's account in the IdP (Keycloak/Authentik/OIDC stub).
- Set `employment_status = "terminated"` or delete the account.
- Bob's next JWT will either fail validation or carry `employment_status != "active"`.

### 2. Verify ABAC Enforcement
- Confirm Qdrant pre-filter includes `user.employment_status == "active"`.
- Confirm Qdrant pre-filter includes `user.clearance_level >= resource.confidentiality_level`.
- Run a test query as Bob (using a terminated test JWT):
  - Expected: empty result set or explicit refusal.
  - Not acceptable: any chunk returned.

### 3. Audit Log Review
- Query the audit log for Bob's recent activity:
  ```sql
  SELECT * FROM audit_log WHERE user_id = 'u_205' ORDER BY timestamp DESC LIMIT 50;
  ```
- Record which chunks Bob last retrieved.

### 4. Re-Classification Check (if needed)
- If Bob owned documents (`owner == 'u_205'`), transfer ownership to a valid user.
- Re-classify any documents that should change tier due to ownership change.
- Re-index only those affected documents (not Bob's entire read history).

## Why No Re-Indexing?
- Chunks carry **resource attributes** (`confidentiality_level`, `department`, `classification`), not user lists.
- Bob's access was gated by his **subject attributes** in the JWT.
- Removing Bob from the IdP removes his attributes; the policy engine denies him automatically.
- Contrast with ACL: would require scanning and re-embedding every chunk Bob could read.

## Related
- ADR 0002: Use ABAC Over ACL for Document Access
- `policy/classification.md`
- `policy/abac.rego`

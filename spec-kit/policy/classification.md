# Data Classification Standard

## Tiers

| Level | Name | Definition | Example |
|-------|------|------------|---------|
| 1 | Public | Anyone in company | Press releases, public onboarding docs |
| 2 | Internal | All employees | Org chart, IT policies, internal wikis |
| 3 | Confidential | Specific departments | Salary bands, product roadmaps, HR handbooks |
| 4 | Restricted | Named individuals | M&A drafts, legal investigations, executive compensation |

## Classification Authority

- The document owner assigns the tier at ingest time.
- A tier cannot be downgraded without security review.
- Reclassification triggers re-indexing: old vectors are deleted, new vectors are embedded with the updated `confidentiality_level`.

## Default

Untagged documents default to **Tier 2 (Internal)**.

## Mapping to ABAC Attributes

- `confidentiality_level` (integer 1–4) is stored on every chunk in Qdrant.
- `user.clearance_level` (integer 1–4) is carried in the JWT subject attributes.
- Access is granted when `user.clearance_level >= chunk.confidentiality_level` **and** department matches.

## Related

- ADR 0002: Use ABAC Over ACL for Document Access
- `schema/chunk-metadata.json`
- `policy/abac.rego`

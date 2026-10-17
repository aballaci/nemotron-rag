#!/usr/bin/env python3
"""Generate synthetic multi-tier company documents for RAG ingestion testing.

Creates markdown files under ./data/raw-documents/ organized by tenant/department,
with accompanying metadata JSON sidecars describing ABAC attributes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("data/raw-documents")
TENANT_ID = "t_acme_corp_001"

DOCUMENTS = [
    # ── Tier 1: Public ──
    {
        "doc_id": "doc-001",
        "title": "Company Press Release Q3 2024",
        "filename": "press-release-q3-2024.md",
        "department": "all",
        "classification": "public",
        "owner": "communications",
        "confidentiality_level": 1,
        "content": """# Company Press Release Q3 2024

Acme Corp reports strong Q3 2024 results with 12% revenue growth year-over-year.
The company expanded into three new markets and hired 50 new employees.

## Key Highlights
- Revenue: $45M (+12% YoY)
- New markets: Germany, Japan, Brazil
- New hires: 50 employees across engineering and sales
- Customer satisfaction: 4.8/5.0

## Contact
Press inquiries: press@acme-corp.com
""",
    },
    {
        "doc_id": "doc-002",
        "title": "Employee Onboarding Guide",
        "filename": "employee-onboarding.md",
        "department": "all",
        "classification": "public",
        "owner": "hr",
        "confidentiality_level": 1,
        "content": """# Employee Onboarding Guide

Welcome to Acme Corp! This guide helps new employees get started.

## First Day
- Arrive at 9:00 AM
- Meet your manager at reception
- Complete HR paperwork
- Set up your laptop and email

## Benefits
- Health insurance
- 25 days PTO
- 401(k) matching
- Learning stipend: $2,000/year

## IT Setup
- VPN: vpn.acme-corp.com
- Email: first.last@acme-corp.com
- Slack: acme-corp.slack.com
""",
    },
    # ── Tier 2: Internal ──
    {
        "doc_id": "doc-003",
        "title": "Engineering Org Chart",
        "filename": "eng-org-chart.md",
        "department": "engineering",
        "classification": "internal",
        "owner": "cto",
        "confidentiality_level": 2,
        "content": """# Engineering Org Chart

## Leadership
- CTO: Sarah Chen
- VP Engineering: Marcus Rodriguez
- Engineering Manager (Platform): Elena Vasquez
- Engineering Manager (Product): David Kim

## Teams

### Platform Team
- Focus: Infrastructure, CI/CD, security
- Members: 8 engineers
- Location: Remote (US, EU)

### Product Team
- Focus: Customer-facing features
- Members: 12 engineers
- Location: Remote (US)

### Security Team
- Focus: Application security, compliance
- Members: 4 engineers
- Location: Remote (US)
""",
    },
    {
        "doc_id": "doc-004",
        "title": "IT Security Policy",
        "filename": "it-security-policy.md",
        "department": "it",
        "classification": "internal",
        "owner": "ciso",
        "confidentiality_level": 2,
        "content": """# IT Security Policy

## Password Requirements
- Minimum 12 characters
- Must include uppercase, lowercase, number, symbol
- Rotate every 90 days
- No reuse of last 5 passwords

## Device Policy
- All laptops must have disk encryption
- Screen lock after 5 minutes
- VPN required for remote access
- No personal devices on corporate network

## Incident Response
- Report security incidents to security@acme-corp.com
- Severity 1: Respond within 1 hour
- Severity 2: Respond within 4 hours
- Severity 3: Respond within 24 hours
""",
    },
    # ── Tier 3: Confidential ──
    {
        "doc_id": "doc-005",
        "title": "2025 Salary Bands - Engineering",
        "filename": "salary-bands-engineering.md",
        "department": "engineering",
        "classification": "compensation",
        "owner": "hr",
        "confidentiality_level": 3,
        "content": """# 2025 Salary Bands - Engineering

CONFIDENTIAL - HR Only

## Salary Bands (USD)

| Level | Title | Min | Mid | Max |
|-------|-------|-----|-----|-----|
| E1 | Junior Engineer | $90,000 | $105,000 | $120,000 |
| E2 | Engineer | $115,000 | $135,000 | $155,000 |
| E3 | Senior Engineer | $145,000 | $170,000 | $195,000 |
| E4 | Staff Engineer | $180,000 | $210,000 | $240,000 |
| E5 | Principal Engineer | $220,000 | $260,000 | $300,000 |

## Bonus Structure
- E1-E2: 10% target bonus
- E3-E4: 15% target bonus
- E5: 20% target bonus

## Equity
- E1-E2: RSU grant $25,000/year
- E3-E4: RSU grant $50,000/year
- E5: RSU grant $100,000/year
""",
    },
    {
        "doc_id": "doc-006",
        "title": "Product Roadmap Q1-Q2 2025",
        "filename": "product-roadmap-2025.md",
        "department": "product",
        "classification": "roadmap",
        "owner": "cpo",
        "confidentiality_level": 3,
        "content": """# Product Roadmap Q1-Q2 2025

CONFIDENTIAL - Product & Leadership Only

## Q1 2025

### AI-Powered Search
- Launch semantic search across knowledge base
- Target: 90% relevance improvement
- Owner: Platform Team

### Mobile App v2.0
- Offline mode
- Push notifications
- Biometric login
- Owner: Product Team

## Q2 2025

### Enterprise SSO
- SAML 2.0 support
- SCIM provisioning
- Audit logging
- Owner: Security Team

### API Rate Limiting
- Tiered limits by plan
- Developer portal
- Owner: Platform Team
""",
    },
    {
        "doc_id": "doc-007",
        "title": "HR Handbook - Leave Policy",
        "filename": "hr-leave-policy.md",
        "department": "hr",
        "classification": "personnel",
        "owner": "hr",
        "confidentiality_level": 3,
        "content": """# HR Handbook - Leave Policy

CONFIDENTIAL - HR and Management Only

## Paid Time Off
- Accrual: 1.67 days/month (20 days/year)
- Max carryover: 10 days
- Request approval: Manager + HR

## Sick Leave
- 10 days/year, no accrual limit
- Doctor's note required for 3+ consecutive days

## Parental Leave
- Birth parent: 16 weeks paid
- Non-birth parent: 8 weeks paid
- Adoption: 12 weeks paid

## Bereavement
- Immediate family: 5 days paid
- Extended family: 3 days paid
""",
    },
    # ── Tier 4: Restricted ──
    {
        "doc_id": "doc-008",
        "title": "M&A Project Alpha - Target Analysis",
        "filename": "ma-project-alpha.md",
        "department": "legal",
        "classification": "m_and_a",
        "owner": "general_counsel",
        "confidentiality_level": 4,
        "content": """# M&A Project Alpha - Target Analysis

RESTRICTED - General Counsel and CEO Only

## Target: Nova Systems Inc.

### Overview
- Industry: FinTech
- Employees: 120
- Revenue: $18M (2023)
- Asking price: $85M-$95M

### Strategic Rationale
- Expands into payment processing
- Adds 50 enterprise customers
- Accelerates AI roadmap by 18 months

### Risks
- Integration complexity
- Customer overlap (15%)
- Regulatory review likely

### Timeline
- LOI: Q1 2025
- Due diligence: Q2 2025
- Close: Q3 2025

## Do Not Share Outside Legal and Executive Team
""",
    },
    {
        "doc_id": "doc-009",
        "title": "Executive Compensation Review",
        "filename": "exec-comp-review.md",
        "department": "executive",
        "classification": "compensation",
        "owner": "board_compensation_committee",
        "confidentiality_level": 4,
        "content": """# Executive Compensation Review

RESTRICTED - Board Compensation Committee Only

## CEO - Sarah Chen
- Base salary: $450,000
- Target bonus: 100% of base
- Equity: $2,000,000 RSUs (4-year vest)

## CFO - Michael Torres
- Base salary: $350,000
- Target bonus: 80% of base
- Equity: $1,200,000 RSUs (4-year vest)

## CTO - Sarah Chen (see above)

## Peer Comparison
- CEO pay at 75th percentile of comparable companies
- CFO pay at 60th percentile

## Do Not Distribute
""",
    },
    {
        "doc_id": "doc-010",
        "title": "Legal Investigation - Vendor Billing",
        "filename": "legal-investigation-vendor.md",
        "department": "legal",
        "classification": "investigation",
        "owner": "general_counsel",
        "confidentiality_level": 4,
        "content": """# Legal Investigation - Vendor Billing Discrepancy

RESTRICTED - General Counsel Only

## Case: Vendor Billing Discrepancy (INV-2024-012)

### Summary
Internal audit identified $450,000 in unverified invoices from CloudScale Inc. over 18 months.

### Findings
- 12 invoices without purchase orders
- 3 invoices for services not rendered
- Vendor overcharged by 22% on cloud storage

### Actions Taken
- Suspended payments to CloudScale Inc.
- Engaged external forensic accountants
- Notified board audit committee

### Status
Ongoing. Expected resolution Q1 2025.

## Strictly Confidential - Legal Only
""",
    },
    {
        "doc_id": "doc-011",
        "title": "HR Investigation - Workplace Complaint",
        "filename": "hr-investigation-workplace.md",
        "department": "hr",
        "classification": "investigation",
        "owner": "hr_director",
        "confidentiality_level": 4,
        "content": """# HR Investigation - Workplace Complaint

RESTRICTED - HR Director and Legal Only

## Case: INV-2024-007

### Complaint
Employee raised concerns about inappropriate comments by a senior manager in Engineering.

### Investigation
- Interviewed 7 witnesses
- Reviewed Slack and email records
- No pattern found prior to this complaint

### Outcome
- Manager received formal warning
- Mandatory leadership training scheduled
- Complainant transferred to different team

### Status
Closed. Documentation retained per retention policy.

## Do Not Share Outside HR and Legal
""",
    },
    {
        "doc_id": "doc-012",
        "title": "IT Incident - Data Breach Attempt",
        "filename": "it-incident-breach-attempt.md",
        "department": "it",
        "classification": "security_incident",
        "owner": "ciso",
        "confidentiality_level": 4,
        "content": """# IT Incident - Data Breach Attempt

RESTRICTED - CISO and CTO Only

## Incident: SEC-2024-045

### Summary
Phishing campaign targeted 15 employees on October 14, 2024.

### Details
- 15 phishing emails sent
- 3 employees clicked malicious link
- 1 employee entered credentials
- Attacker accessed one email account for 4 hours

### Response
- Account locked immediately
- Password reset for all 15 employees
- MFA enforced for all accounts
- Security awareness training deployed

### Impact
- No customer data accessed
- No systems compromised
- No regulatory notification required

## Restricted - CISO and CTO Only
""",
    },
]


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    metadata = []

    for doc in DOCUMENTS:
        # Create department subdirectory
        dept_dir = ROOT / TENANT_ID / doc["department"]
        dept_dir.mkdir(parents=True, exist_ok=True)

        # Write markdown file
        md_path = dept_dir / doc["filename"]
        md_path.write_text(doc["content"], encoding="utf-8")

        # Write metadata sidecar
        meta = {
            "doc_id": doc["doc_id"],
            "title": doc["title"],
            "source_path": str(md_path),
            "confidentiality_level": doc["confidentiality_level"],
            "department": doc["department"],
            "classification": doc["classification"],
            "owner": doc["owner"],
            "tenant_id": TENANT_ID,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        meta_path = dept_dir / (doc["filename"].replace(".md", ".meta.json"))
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        metadata.append(meta)

    # Write master metadata index
    index_path = ROOT / TENANT_ID / "index.json"
    index_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Created {len(DOCUMENTS)} documents under {ROOT / TENANT_ID}")
    print("Tiers:", {d["doc_id"]: d["confidentiality_level"] for d in DOCUMENTS})
    print("Departments:", sorted(set(d["department"] for d in DOCUMENTS)))


if __name__ == "__main__":
    main()

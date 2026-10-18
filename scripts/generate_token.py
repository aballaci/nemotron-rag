#!/usr/bin/env python3
"""Generate a dev JWT for the RAG API.

The signing secret is resolved like the API does (JWT_SECRET_FILE, then
JWT_SECRET, then the dev default), falling back to secrets/jwt_secret.txt
when run from the host.

Usage:
    python scripts/generate_token.py
    python scripts/generate_token.py --persona diana
    python scripts/generate_token.py --list-personas
    python scripts/generate_token.py --persona marcus --clearance 4   # override
    python scripts/generate_token.py --department finance --clearance 3 --ttl 86400
    curl -H "Authorization: Bearer $(python scripts/generate_token.py)" ...
"""

from __future__ import annotations

import argparse
import os
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from adapters.auth.jwt_adapter import JWTAdapter  # noqa: E402
from adapters.auth.settings import load_jwt_secret  # noqa: E402


# Same personas as scripts/console_rag.py
PERSONAS = {
    "alice": dict(user="u_alice", roles="engineer", department="engineering", clearance=2),
    "marcus": dict(user="u_marcus", roles="manager", department="engineering", clearance=3),
    "diana": dict(user="u_diana", roles="legal_counsel", department="legal", clearance=4),
    "stranger": dict(user="u_stranger", tenant="t_other_company", roles="admin", department="engineering", clearance=4),
    "bob": dict(user="u_bob", roles="intern", department="hr", clearance=1, status="inactive"),
}
DEFAULTS = dict(
    user="u_alice", tenant="t_acme_corp_001", roles="engineer",
    department="engineering", clearance=2, status="active",
)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--persona", choices=sorted(PERSONAS), help="preset user (flags below override it)")
    p.add_argument("--list-personas", action="store_true", help="show presets and exit")
    p.add_argument("--user")
    p.add_argument("--tenant")
    p.add_argument("--roles", help="comma-separated")
    p.add_argument("--department")
    p.add_argument("--clearance", type=int)
    p.add_argument("--status", help="employment_status")
    p.add_argument("--contractor", action="store_true")
    p.add_argument("--ttl", type=int, default=3600, help="seconds")
    args = p.parse_args()

    if args.list_personas:
        for name, v in PERSONAS.items():
            c = {**DEFAULTS, **v}
            print(f"{name:9} {c['user']:11} {c['tenant']:16} {c['department']:12} "
                  f"clearance={c['clearance']} {c['status']} roles={c['roles']}")
        return

    base = {**DEFAULTS, **PERSONAS.get(args.persona, {})}
    for key in DEFAULTS:
        if getattr(args, key) is None:
            setattr(args, key, base[key])

    if not os.getenv("JWT_SECRET_FILE"):
        host_secret = ROOT / "secrets" / "jwt_secret.txt"
        if host_secret.exists():
            os.environ["JWT_SECRET_FILE"] = str(host_secret)

    warnings.filterwarnings("ignore")  # short dev HMAC key warning
    token = JWTAdapter(secret=load_jwt_secret()).generate_test_token(
        user_id=args.user,
        tenant_id=args.tenant,
        roles=[r for r in args.roles.split(",") if r],
        department=args.department,
        clearance_level=args.clearance,
        employment_status=args.status,
        contractor=args.contractor,
        ttl_seconds=args.ttl,
    )
    print(token)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate a dev JWT for the RAG API.

The signing secret is resolved like the API does (JWT_SECRET_FILE, then
JWT_SECRET, then the dev default), falling back to secrets/jwt_secret.txt
when run from the host.

Usage:
    python scripts/generate_token.py
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


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--user", default="u_alice")
    p.add_argument("--tenant", default="t_acme_corp_001")
    p.add_argument("--roles", default="engineer", help="comma-separated")
    p.add_argument("--department", default="engineering")
    p.add_argument("--clearance", type=int, default=2)
    p.add_argument("--status", default="active", help="employment_status")
    p.add_argument("--contractor", action="store_true")
    p.add_argument("--ttl", type=int, default=3600, help="seconds")
    args = p.parse_args()

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

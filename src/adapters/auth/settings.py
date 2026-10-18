"""Resolve the JWT signing secret from a mounted secret file or env."""

from __future__ import annotations

import os

DEFAULT_JWT_SECRET = "changeme-please-replace-with-a-strong-secret"


def load_jwt_secret() -> str:
    path = os.getenv("JWT_SECRET_FILE")
    if path and os.path.exists(path):
        with open(path) as f:
            value = f.read().strip()
        if value:
            return value
    return os.getenv("JWT_SECRET") or DEFAULT_JWT_SECRET

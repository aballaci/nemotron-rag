"""JWT authentication adapter.

Validates OpenID Connect JWTs and extracts subject attributes for ABAC.
Implements AuthPort.
"""

from __future__ import annotations

import time
from typing import Any

import jwt

from core.models import UserContext
from ports.auth_port import AuthPort


class JWTAdapter(AuthPort):
    """AuthPort implementation using PyJWT.

    Validates JWT signature and extracts subject attributes required for ABAC:
    user_id, tenant_id, roles, department, clearance_level, location,
    employment_status, contractor.
    """

    def __init__(self, secret: str, algorithm: str = "HS256"):
        self.secret = secret
        self.algorithm = algorithm

    def validate_token(self, token: str) -> UserContext:
        """Validate a JWT and return user context.

        Raises jwt.InvalidTokenError if the token is invalid or expired.
        """
        payload: dict[str, Any] = jwt.decode(
            token,
            self.secret,
            algorithms=[self.algorithm],
            options={"verify_exp": True},
        )

        return UserContext(
            user_id=payload.get("sub", ""),
            tenant_id=payload.get("tenant_id", ""),
            roles=payload.get("roles", []),
            department=payload.get("department", ""),
            clearance_level=int(payload.get("clearance_level", 0)),
            location=payload.get("location", ""),
            employment_status=payload.get("employment_status", "inactive"),
            contractor=payload.get("contractor", False),
        )

    def has_clearance(self, user_context: UserContext, required_level: int) -> bool:
        """Check if user meets clearance level."""
        return user_context.clearance_level >= required_level

    def generate_test_token(
        self,
        user_id: str,
        tenant_id: str,
        roles: list[str],
        department: str,
        clearance_level: int,
        employment_status: str = "active",
        contractor: bool = False,
        ttl_seconds: int = 3600,
    ) -> str:
        """Generate a test JWT (for development and testing only)."""
        now = int(time.time())
        payload = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "roles": roles,
            "department": department,
            "clearance_level": clearance_level,
            "location": "US",
            "employment_status": employment_status,
            "contractor": contractor,
            "iat": now,
            "exp": now + ttl_seconds,
        }
        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

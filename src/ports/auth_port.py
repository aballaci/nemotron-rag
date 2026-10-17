"""Auth port interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.models import UserContext


class AuthPort(ABC):
    """Port for authentication and authorization."""

    @abstractmethod
    def validate_token(self, token: str) -> UserContext:
        """Validate a JWT and return user context."""

    @abstractmethod
    def has_clearance(self, user_context: UserContext, required_level: int) -> bool:
        """Check if user meets clearance level."""

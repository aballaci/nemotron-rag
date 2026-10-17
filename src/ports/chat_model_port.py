"""Chat model port interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ChatModelPort(ABC):
    """Port for chat/completion model inference."""

    @abstractmethod
    def generate_answer(
        self,
        system_prompt: str,
        user_question: str,
        temperature: float = 0.2,
    ) -> str:
        """Generate an answer given system context and user question."""

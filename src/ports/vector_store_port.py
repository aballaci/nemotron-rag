"""Ports (interfaces) for the RAG agent.

Hexagonal architecture: business logic depends on these interfaces,
not on concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from core.models import Chunk, RetrievalResult, UserContext


class EmbeddingPort(ABC):
    """Port for generating embeddings from text."""

    @abstractmethod
    def embed_passage(self, texts: List[str]) -> List[List[float]]:
        """Embed documents for indexing (input_type: passage)."""

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Embed a single search query (input_type: query)."""


class VectorStorePort(ABC):
    """Port for vector storage and similarity search with ABAC pre-filtering."""

    @abstractmethod
    def create_collection(self) -> None:
        """Ensure the vector collection exists with correct schema."""

    @abstractmethod
    def upsert_chunks(self, chunks: List[Chunk], vectors: List[List[float]]) -> List[str]:
        """Write chunk vectors and metadata to the store. Returns vector IDs."""

    @abstractmethod
    def search(
        self,
        query_vector: List[float],
        user_context: UserContext,
        top_k: int = 5,
    ) -> List[RetrievalResult]:
        """Search for similar chunks, pre-filtered by user attributes."""

    @abstractmethod
    def delete_chunks_by_doc(self, doc_id: str) -> int:
        """Delete all chunks for a document. Returns count deleted."""


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


class AuthPort(ABC):
    """Port for authentication and authorization."""

    @abstractmethod
    def validate_token(self, token: str) -> UserContext:
        """Validate a JWT and return user context."""

    @abstractmethod
    def has_clearance(self, user_context: UserContext, required_level: int) -> bool:
        """Check if user meets clearance level."""


class DocumentStorePort(ABC):
    """Port for raw document storage (MinIO)."""

    @abstractmethod
    def upload(self, tenant_id: str, doc_id: str, data: bytes) -> str:
        """Upload a document. Returns object path."""

    @abstractmethod
    def download(self, object_path: str) -> bytes:
        """Download a document."""

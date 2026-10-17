"""Embedding port interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class EmbeddingPort(ABC):
    """Port for generating embeddings from text."""

    @abstractmethod
    def embed_passage(self, texts: List[str]) -> List[List[float]]:
        """Embed documents for indexing (input_type: passage)."""

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Embed a single search query (input_type: query)."""

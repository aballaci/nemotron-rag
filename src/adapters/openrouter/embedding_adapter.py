"""OpenRouter embedding adapter.

Calls OpenRouter /v1/embeddings with nvidia/nemotron-3-embed-1b.
"""

from __future__ import annotations

from typing import List

import requests

from ports.embedding_port import EmbeddingPort

EMBED_MODEL_ID = "nvidia/nemotron-3-embed-1b:free"


class OpenRouterEmbeddingAdapter(EmbeddingPort):
    """OpenRouter implementation of EmbeddingPort."""

    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def embed_passage(self, texts: List[str]) -> List[List[float]]:
        """Embed documents for indexing (input_type: passage)."""
        return self._embed(texts, input_type="passage")

    def embed_query(self, text: str) -> List[float]:
        """Embed a single search query (input_type: query)."""
        vectors = self._embed([text], input_type="query")
        return vectors[0]

    def _embed(self, texts: List[str], input_type: str) -> List[List[float]]:
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": EMBED_MODEL_ID,
            "input": texts,
            "input_type": input_type,
            "encoding_format": "float",
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        return [item["embedding"] for item in data["data"]]

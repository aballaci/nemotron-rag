"""Document store port interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class DocumentStorePort(ABC):
    """Port for raw document storage (MinIO/S3-compatible)."""

    @abstractmethod
    def upload(self, tenant_id: str, doc_id: str, data: bytes) -> str:
        """Upload a document. Returns object path."""

    @abstractmethod
    def download(self, object_path: str) -> bytes:
        """Download a document."""

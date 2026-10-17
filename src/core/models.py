"""Domain models for the RAG agent.

Pure Python dataclasses — no framework imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Chunk:
    """A document chunk with ABAC metadata for vector indexing."""

    chunk_id: str
    doc_id: str
    text: str
    confidentiality_level: int  # 1=public, 2=internal, 3=confidential, 4=restricted
    department: str
    classification: str
    owner: str
    chunk_index: int = 0
    token_count: Optional[int] = None
    vector_id: Optional[str] = None
    updated_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Document:
    """Source document record."""

    doc_id: str
    title: str
    source_path: str
    confidentiality_level: int
    department: str
    classification: str
    owner: str
    updated_at: Optional[datetime] = None
    status: str = "ingesting"
    created_at: Optional[datetime] = None


@dataclass
class UserContext:
    """Authenticated user attributes extracted from JWT."""

    user_id: str
    tenant_id: str
    roles: List[str]
    department: str
    clearance_level: int
    location: str
    employment_status: str
    contractor: bool = False


@dataclass
class RetrievalResult:
    """A chunk returned from retrieval with its similarity score."""

    chunk: Chunk
    score: float


@dataclass
class IngestionResult:
    """Result of ingesting a document."""

    doc_id: str
    chunks_indexed: int
    vectors_written: int
    status: str

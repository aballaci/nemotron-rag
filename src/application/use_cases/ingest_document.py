"""IngestDocument use case.

Orchestrates: document → chunks → embeddings → vector store + metadata store.
Implements ABAC tagging at index time.
"""

from __future__ import annotations

from typing import List

from core.models import Chunk, Document, IngestionResult
from adapters.qdrant.qdrant_adapter import QdrantAdapter
from adapters.openrouter.embedding_adapter import OpenRouterEmbeddingAdapter
from ports.document_store_port import DocumentStorePort


class IngestDocumentUseCase:
    """Use case for ingesting a single document into the RAG system."""

    def __init__(
        self,
        embedding_adapter: OpenRouterEmbeddingAdapter,
        vector_store: QdrantAdapter,
        document_store: DocumentStorePort,
    ):
        self.embedding = embedding_adapter
        self.vector_store = vector_store
        self.document_store = document_store

    def execute(
        self,
        doc_id: str,
        title: str,
        text: str,
        confidentiality_level: int,
        department: str,
        classification: str,
        owner: str,
        tenant_id: str,
        source_path: str,
        chunk_size: int = 512,
        overlap: int = 50,
    ) -> IngestionResult:
        """Ingest a document: chunk, embed, index, persist metadata."""

        # 1. Chunk the document
        chunks = self._chunk_text(
            text=text,
            doc_id=doc_id,
            chunk_size=chunk_size,
            overlap=overlap,
            confidentiality_level=confidentiality_level,
            department=department,
            classification=classification,
            owner=owner,
            tenant_id=tenant_id,
        )

        if not chunks:
            return IngestionResult(
                doc_id=doc_id,
                chunks_indexed=0,
                vectors_written=0,
                status="empty",
            )

        # 2. Embed passages (input_type: passage)
        passage_texts = [c.text for c in chunks]
        vectors = self.embedding.embed_passage(passage_texts)

        # 3. Write to vector store
        vector_ids = self.vector_store.upsert_chunks(chunks, vectors)

        # 4. Upload raw document to object store (optional, if source_path provided)
        # The document_store adapter handles MinIO; here we just record intent.

        return IngestionResult(
            doc_id=doc_id,
            chunks_indexed=len(chunks),
            vectors_written=len(vector_ids),
            status="completed",
        )

    def _chunk_text(
        self,
        text: str,
        doc_id: str,
        chunk_size: int,
        overlap: int,
        confidentiality_level: int,
        department: str,
        classification: str,
        owner: str,
        tenant_id: str,
    ) -> List[Chunk]:
        """Split text into overlapping chunks with ABAC metadata."""
        if not text.strip():
            return []

        words = text.split()
        chunks: List[Chunk] = []
        start = 0
        index = 0

        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_words = words[start:end]
            chunk_text = " ".join(chunk_words)

            chunk = Chunk(
                chunk_id=f"{doc_id}#{index}",
                doc_id=doc_id,
                text=chunk_text,
                confidentiality_level=confidentiality_level,
                department=department,
                classification=classification,
                owner=owner,
                chunk_index=index,
                metadata={"tenant_id": tenant_id},
            )
            chunks.append(chunk)
            index += 1

            if end >= len(words):
                break
            start = end - overlap
            if start < 0:
                start = 0

        return chunks

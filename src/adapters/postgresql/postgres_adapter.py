"""PostgreSQL metadata adapter.

Persists document records, chunk metadata, and audit log entries.
Implements DocumentStorePort implicitly (metadata only; raw objects go to MinIO).
"""

from __future__ import annotations

from typing import Any

import psycopg2
import psycopg2.extras

from core.models import Chunk, Document


class PostgresAdapter:
    """PostgreSQL implementation of metadata persistence."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    def _connect(self):
        return psycopg2.connect(self.dsn)

    def create_document(self, document: Document) -> None:
        """Insert a document record."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents
                    (doc_id, title, source_path, confidentiality_level,
                     department, classification, owner, updated_at, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (doc_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        source_path = EXCLUDED.source_path,
                        confidentiality_level = EXCLUDED.confidentiality_level,
                        department = EXCLUDED.department,
                        classification = EXCLUDED.classification,
                        owner = EXCLUDED.owner,
                        updated_at = EXCLUDED.updated_at,
                        status = EXCLUDED.status
                    """,
                    (
                        document.doc_id,
                        document.title,
                        document.source_path,
                        document.confidentiality_level,
                        document.department,
                        document.classification,
                        document.owner,
                        document.updated_at,
                        document.status,
                    ),
                )
            conn.commit()

    def create_chunks(self, chunks: list[Chunk]) -> None:
        """Insert chunk metadata records."""
        if not chunks:
            return
        with self._connect() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO chunks
                    (chunk_id, doc_id, chunk_index, text, token_count,
                     vector_id, confidentiality_level, department,
                     classification, owner, updated_at)
                    VALUES %s
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        text = EXCLUDED.text,
                        token_count = EXCLUDED.token_count,
                        vector_id = EXCLUDED.vector_id,
                        confidentiality_level = EXCLUDED.confidentiality_level,
                        department = EXCLUDED.department,
                        classification = EXCLUDED.classification,
                        owner = EXCLUDED.owner,
                        updated_at = EXCLUDED.updated_at
                    """,
                    [
                        (
                            c.chunk_id,
                            c.doc_id,
                            c.chunk_index,
                            c.text,
                            c.token_count,
                            c.vector_id,
                            c.confidentiality_level,
                            c.department,
                            c.classification,
                            c.owner,
                            c.updated_at,
                        )
                        for c in chunks
                    ],
                )
            conn.commit()

    def log_audit(
        self,
        user_id: str,
        query_hash: str,
        retrieved_chunk_ids: list[str],
        model: str,
        latency_ms: int,
        tier_filter_applied: bool = True,
        answer_generated: bool = False,
        refusal_reason: str | None = None,
    ) -> None:
        """Insert an audit log entry."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_log
                    (user_id, query_hash, retrieved_chunk_ids, model,
                     latency_ms, tier_filter_applied, answer_generated,
                     refusal_reason)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        query_hash,
                        retrieved_chunk_ids,
                        model,
                        latency_ms,
                        tier_filter_applied,
                        answer_generated,
                        refusal_reason,
                    ),
                )
            conn.commit()

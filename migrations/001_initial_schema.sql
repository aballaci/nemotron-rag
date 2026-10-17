-- Phase 1: Initial schema for RAG metadata store
-- Runs automatically on postgres container first start via docker-entrypoint-initdb.d

CREATE TABLE IF NOT EXISTS documents (
    doc_id VARCHAR(255) PRIMARY KEY,
    title VARCHAR(512) NOT NULL,
    source_path TEXT NOT NULL,
    confidentiality_level INTEGER NOT NULL CHECK (confidentiality_level BETWEEN 1 AND 4),
    department VARCHAR(128) NOT NULL,
    classification VARCHAR(128),
    owner VARCHAR(255) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(32) NOT NULL DEFAULT 'ingesting',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id VARCHAR(255) PRIMARY KEY,
    doc_id VARCHAR(255) NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    token_count INTEGER,
    vector_id VARCHAR(255) NOT NULL,
    confidentiality_level INTEGER NOT NULL CHECK (confidentiality_level BETWEEN 1 AND 4),
    department VARCHAR(128) NOT NULL,
    classification VARCHAR(128),
    owner VARCHAR(255) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunks_confidentiality ON chunks(confidentiality_level);
CREATE INDEX IF NOT EXISTS idx_chunks_department ON chunks(department);

CREATE TABLE IF NOT EXISTS audit_log (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id VARCHAR(255) NOT NULL,
    query_hash VARCHAR(64) NOT NULL,
    retrieved_chunk_ids TEXT[] NOT NULL DEFAULT '{}',
    model VARCHAR(255) NOT NULL,
    latency_ms INTEGER NOT NULL,
    tier_filter_applied BOOLEAN NOT NULL DEFAULT TRUE,
    answer_generated BOOLEAN NOT NULL DEFAULT FALSE,
    refusal_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_user_id ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

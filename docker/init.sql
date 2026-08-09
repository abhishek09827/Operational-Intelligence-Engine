-- Create incidents table
-- Milestone 1 (v2): restore native pgvector with HNSW indexing.
CREATE EXTENSION IF NOT EXISTS vector;

-- Service runbooks: grounded remediation steps retrieved by the swarm's Runbook Agent.
-- Row = chunk of a markdown runbook; embedding is 768-dim (matches EmbeddingService).
CREATE TABLE IF NOT EXISTS runbooks (
    id BIGSERIAL PRIMARY KEY,
    service_name TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (service_name, source, chunk_index)
);

CREATE INDEX IF NOT EXISTS runbooks_embedding_hnsw
    ON runbooks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS runbooks_service_idx ON runbooks(service_name);

CREATE TABLE IF NOT EXISTS incidents (
    id SERIAL PRIMARY KEY,
    title VARCHAR NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR DEFAULT 'Open',
    severity VARCHAR DEFAULT 'Medium',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    root_cause TEXT,
    suggested_fix TEXT,
    confidence_score FLOAT,
    embedding JSON
);

-- Create index for efficient search (optional, can be used for text search)
CREATE INDEX IF NOT EXISTS incidents_title_idx ON incidents(title);
CREATE INDEX IF NOT EXISTS incidents_status_idx ON incidents(status);

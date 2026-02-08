-- Create incidents table
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

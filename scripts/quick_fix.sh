#!/bin/bash

# Quick fix script to update the database schema
# This is a minimal approach to fix the dimension mismatch

echo "Stopping database container..."
docker-compose stop db

echo ""
echo "Removing database volume (will delete all data)..."
docker-compose down -v

echo ""
echo "Starting database with new schema..."
docker-compose up -d db

echo ""
echo "Waiting for database to be ready..."
sleep 15

echo ""
echo "Applying schema changes..."
docker-compose exec -T db psql -U opsuser -d opspilot << 'EOF'
-- Update the existing incidents table
ALTER TABLE incidents ALTER COLUMN embedding TYPE vector(768);
DROP INDEX IF EXISTS incidents_embedding_idx;
CREATE INDEX incidents_embedding_idx ON incidents USING hnsw (embedding vector_cosine_ops);
EOF

echo ""
echo "✅ Database schema updated successfully!"
echo ""
echo "Restarting application containers..."
docker-compose restart app-1 app-2 app-3

echo ""
echo "Note: All existing incident data has been lost. You'll need to re-analyze your logs."
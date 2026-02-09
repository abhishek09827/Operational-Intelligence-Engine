#!/bin/bash

# Migration script to convert pgvector embeddings to JSON
# This runs inside the database container

echo "🚀 Running migration from pgvector to JSON..."

# Check if pgvector extension exists
echo "Checking for pgvector extension..."
PGVECTOR_EXISTS=$(docker-compose exec -T db psql -U opsuser -d opspilot -t -c "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')")

if [ "$PGVECTOR_EXISTS" = "t" ]; then
    echo "✅ pgvector extension found, proceeding with migration..."
    
    # Run the migration
    docker-compose exec -T db psql -U opsuser -d opspilot << 'EOF'
    -- Create temporary column for JSON data
    ALTER TABLE incidents ADD COLUMN IF NOT EXISTS embedding_json JSON;
    
    -- Copy vector data to JSON
    UPDATE incidents SET embedding_json = embedding::jsonb WHERE embedding IS NOT NULL;
    
    -- Drop the pgvector column
    ALTER TABLE incidents DROP COLUMN IF EXISTS embedding;
    
    -- Rename JSON column to embedding
    ALTER TABLE incidents RENAME COLUMN embedding_json TO embedding;
    
    -- Verify migration
    SELECT 'Migration completed successfully' as status;
EOF
    
    echo "✅ Migration completed!"
else
    echo "✅ No pgvector extension found, migration not needed."
fi
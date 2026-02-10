# Embedding Migration: pgvector to JSON Storage

## Overview
This migration converts the incident embeddings from using PostgreSQL's pgvector extension to storing embeddings as JSON. This approach provides greater flexibility and avoids dimension mismatch issues.

## Why Change to JSON Storage?

### Benefits:
1. **Flexible Dimensionality**: Can store embeddings of any dimension without database schema changes
2. **Easier Model Switching**: Easily switch between different embedding models (Gemini, OpenAI, etc.)
3. **No pgvector Dependency**: Simplifies database setup and reduces dependencies
4. **Better Compatibility**: Works with all PostgreSQL versions (no special extensions needed)

### What Changed:
- **Before**: `embedding = Column(Vector(3072))` - Required pgvector extension
- **After**: `embedding = Column(JSON)` - Stores embeddings as list of floats

## Migration Steps

### Option 1: Quick Migration (Recommended for existing databases)

#### Windows:
```bash
scripts\run_migration.sh
```

#### Linux/Mac:
```bash
chmod +x scripts/run_migration.sh
./scripts/run_migration.sh
```

### Option 2: Full Database Rebuild

#### Windows:
```bash
scripts\quick_fix.bat
```

#### Linux/Mac:
```bash
chmod +x scripts/quick_fix.sh
./scripts/quick_fix.sh
```

## What the Migration Does

### Quick Migration:
1. Checks if pgvector extension exists
2. Converts vector data to JSON
3. Drops the pgvector column
4. Renames JSON column to embedding
5. Leaves existing data intact

### Full Rebuild:
1. Stops database container
2. Removes database volume (deletes all data)
3. Creates fresh database with JSON schema
4. Restarts application containers

## Updated Code

### app/models/incident.py
```python
from sqlalchemy import Column, Integer, String, DateTime, Float, Text, JSON

class Incident(Base):
    # ...
    # RAG Embeddings stored as JSON string (list of floats)
    embedding = Column(JSON, nullable=True)
```

### app/rag/vector_db.py
- Now calculates cosine similarity manually instead of using pgvector functions
- Fetches all incidents with embeddings
- Filters by similarity threshold
- Returns sorted results

### docker/init.sql
- Removed pgvector extension requirement
- Changed embedding column to JSON type
- Added standard text indexes for title and status

### requirements.txt
- Removed `pgvector>=0.2.4`

## How to Verify the Migration

1. Check the database schema:
```bash
docker-compose exec -T db psql -U opsuser -d opspilot -c "\d incidents"
```

2. Look for the embedding column type - it should show "json" not "vector"

3. Test the application:
- Trigger an incident analysis
- Verify no dimension mismatch errors occur
- Check that embeddings are stored correctly

## Future Benefits

### Easy Model Switching:
```python
# Change embedding model without database changes
# Just update the model name in config
settings.GEMINI_EMBEDDING_MODEL = "your-new-model"
```

### Support Multiple Embedding Models:
```python
# Store different models' embeddings together
incident.embedding = {"model": "gemini-embedding-001", "data": [0.1, 0.2, ...]}
```

### Easy Export/Import:
```python
# Export embeddings as JSON for backup or sharing
```

## Notes

- The migration is reversible if needed
- All existing vector embeddings will be converted to JSON
- After migration, you don't need to rebuild the database for new embedding models
- The system is now much more flexible for future changes
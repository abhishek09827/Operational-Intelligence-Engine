# Fix: Dimension Mismatch Error

## Problem
The application was encountering a dimension mismatch error:
```
psycopg2.errors.DataException: expected 768 dimensions, not 3072
```

## Root Cause
- The database schema was configured to store **3072-dimensional** vectors
- The Gemini embedding model (`gemini-embedding-001`) produces **768-dimensional** vectors

## Solution Implemented
Updated `docker/init.sql` to change the embedding vector dimension from `vector(3072)` to `vector(768)` to match the Gemini embedding model.

## How to Apply the Fix

### Windows Users (Quick Fix - Recommended)
```bash
scripts\quick_fix.bat
```

### Linux/Mac Users (Quick Fix - Recommended)
```bash
chmod +x scripts/quick_fix.sh
./scripts/quick_fix.sh
```

### Alternative: Full Database Rebuild
```bash
scripts\rebuild_database.bat
```

### Manual Steps (if scripts fail)
1. Stop the database container:
   ```bash
   docker-compose stop db
   ```

2. Remove database volume (this deletes all data):
   ```bash
   docker-compose down -v
   ```

3. Start database with new schema:
   ```bash
   docker-compose up -d db
   ```

4. Apply initialization scripts:
   ```bash
   docker-compose exec -T db psql -U opsuser -d opspilot < docker/init.sql
   ```

5. Restart application containers:
   ```bash
   docker-compose restart app-1 app-2 app-3
   ```

## Verification
After rebuilding the database, the application should no longer encounter the dimension mismatch error. The RAG search functionality will work correctly with the Gemini embedding model.

## Notes
- All existing data will be lost during the database rebuild
- Make sure you have backups if you need to preserve existing incident data
- The fix aligns the database schema with the standard Gemini embedding model dimension
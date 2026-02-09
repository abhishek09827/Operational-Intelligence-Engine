"""
Migration script to convert pgvector embeddings to JSON storage.
This script will convert existing vector(3072) columns to JSON and remove pgvector dependency.
"""

import sys
import json
from sqlalchemy import create_engine, text, inspect

# Database connection string (should be set in environment or config)
DB_URL = sys.argv[1] if len(sys.argv) > 1 else "postgresql://opsuser:opspassword@localhost:5432/opspilot"

def migrate_embeddings():
    """Migrate pgvector embeddings to JSON storage."""
    print("🚀 Starting migration from pgvector to JSON...")
    print(f"Database URL: {DB_URL}")
    
    engine = create_engine(DB_URL)
    
    try:
        with engine.connect() as conn:
            # Check if pgvector extension exists
            result = conn.execute(text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"))
            if not result.scalar():
                print("✅ No pgvector extension found, migration not needed.")
                return
            
            print("✅ pgvector extension found, proceeding with migration...")
            
            # Start transaction
            conn.begin()
            
            # Step 1: Create temporary column for JSON data
            print("\n📝 Step 1: Creating temporary JSON column...")
            conn.execute(text("""
                ALTER TABLE incidents 
                ADD COLUMN IF NOT EXISTS embedding_json JSON
            """))
            
            # Step 2: Copy vector data to JSON
            print("\n📝 Step 2: Converting vector data to JSON...")
            conn.execute(text("""
                UPDATE incidents 
                SET embedding_json = embedding::jsonb
                WHERE embedding IS NOT NULL
            """))
            
            # Step 3: Drop the pgvector column
            print("\n📝 Step 3: Dropping pgvector column...")
            conn.execute(text("""
                ALTER TABLE incidents 
                DROP COLUMN IF EXISTS embedding
            """))
            
            # Step 4: Rename JSON column to embedding
            print("\n📝 Step 4: Renaming JSON column to embedding...")
            conn.execute(text("""
                ALTER TABLE incidents 
                RENAME COLUMN embedding_json TO embedding
            """))
            
            # Commit transaction
            conn.commit()
            
            # Verify migration
            print("\n✅ Verifying migration...")
            inspector = inspect(engine)
            columns = [col['name'] for col in inspector.get_columns('incidents')]
            
            if 'embedding' in columns and inspector.get_columns('incidents')[columns.index('embedding')]['type'].python_type == dict:
                print("✅ Migration successful! Embeddings are now stored as JSON.")
                print(f"\n📊 Current incident count: {inspector.get_table_names()[0]}")
            else:
                print("⚠️  Migration completed but verification failed.")
            
            print("\n🎉 Migration complete!")
            
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        if 'conn' in locals() and conn.in_transaction():
            conn.rollback()
        sys.exit(1)

if __name__ == "__main__":
    migrate_embeddings()
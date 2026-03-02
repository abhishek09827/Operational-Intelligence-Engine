"""
Migration script to add thinking_process column to incidents table
"""
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Create a separate engine for migration
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def migrate():
    """Add thinking_process column to incidents table"""
    try:
        print("Starting migration: adding thinking_process column to incidents table...")
        
        with engine.connect() as conn:
            # Check if column already exists
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'incidents' 
                AND column_name = 'thinking_process'
            """)
            
            result = conn.execute(check_query)
            column_exists = result.fetchone()
            
            if column_exists:
                print("✅ Column 'thinking_process' already exists in incidents table.")
                return
            
            # Add the column
            add_column = text("""
                ALTER TABLE incidents 
                ADD COLUMN thinking_process TEXT
            """)
            
            conn.execute(add_column)
            conn.commit()
            
            print("✅ Successfully added 'thinking_process' column to incidents table.")
            
            # Verify the column was added
            result = conn.execute(check_query)
            if result.fetchone():
                print("✅ Column verification successful.")
        
        print("\nMigration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
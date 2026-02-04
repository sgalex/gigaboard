"""Quick script to add EXTRACT to edgetype enum"""
import asyncio
import asyncpg
from app.core.config import settings

async def main():
    # Connect to database
    conn = await asyncpg.connect(settings.DATABASE_URL.replace('+asyncpg', ''))
    
    try:
        # Check current enum values
        result = await conn.fetch("SELECT unnest(enum_range(NULL::edgetype))::text as value")
        print("Current edgetype values:")
        for row in result:
            print(f"  - {row['value']}")
        
        if any(row['value'] == 'EXTRACT' for row in result):
            print("\n✅ EXTRACT already exists in enum!")
            return
        
        print("\n🔧 Adding EXTRACT to enum...")
        
        # Alter column to text
        await conn.execute("ALTER TABLE edges ALTER COLUMN edge_type TYPE VARCHAR(50)")
        print("  ✓ Column converted to VARCHAR")
        
        # Drop old enum
        await conn.execute("DROP TYPE IF EXISTS edgetype")
        print("  ✓ Old enum dropped")
        
        # Create new enum with EXTRACT
        await conn.execute("""
            CREATE TYPE edgetype AS ENUM (
                'EXTRACT',
                'TRANSFORMATION',
                'VISUALIZATION', 
                'COMMENT',
                'DRILL_DOWN',
                'REFERENCE'
            )
        """)
        print("  ✓ New enum created with EXTRACT")
        
        # Alter column back to enum
        await conn.execute("ALTER TABLE edges ALTER COLUMN edge_type TYPE edgetype USING edge_type::edgetype")
        print("  ✓ Column converted back to enum")
        
        # Verify
        result = await conn.fetch("SELECT unnest(enum_range(NULL::edgetype))::text as value")
        print("\n✅ Updated edgetype values:")
        for row in result:
            print(f"  - {row['value']}")
            
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())

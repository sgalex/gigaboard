"""
Fix orphaned source_nodes before running migration
Deletes source_nodes that don't have corresponding content_nodes
"""
import asyncio
from sqlalchemy import text
from app.core.database import engine


async def fix_orphaned_nodes():
    async with engine.begin() as conn:
        # Find orphaned source_nodes
        result = await conn.execute(text("""
            SELECT id FROM source_nodes 
            WHERE id NOT IN (SELECT id FROM content_nodes)
        """))
        orphaned = result.fetchall()
        
        if orphaned:
            print(f"Found {len(orphaned)} orphaned source_nodes:")
            for row in orphaned:
                print(f"  - {row.id}")
            
            # Delete orphaned source_nodes
            await conn.execute(text("""
                DELETE FROM source_nodes 
                WHERE id NOT IN (SELECT id FROM content_nodes)
            """))
            print(f"✅ Deleted {len(orphaned)} orphaned source_nodes")
        else:
            print("✅ No orphaned source_nodes found")
        
        # Also check and update EXTRACT edges
        result = await conn.execute(text("""
            SELECT COUNT(*) as count FROM edges WHERE edge_type = 'EXTRACT'
        """))
        extract_count = result.scalar()
        
        if extract_count:
            print(f"\nFound {extract_count} EXTRACT edges")
            await conn.execute(text("""
                UPDATE edges SET edge_type = 'TRANSFORMATION' 
                WHERE edge_type = 'EXTRACT'
            """))
            print(f"✅ Updated {extract_count} EXTRACT edges to TRANSFORMATION")
        else:
            print("\n✅ No EXTRACT edges found")


if __name__ == "__main__":
    asyncio.run(fix_orphaned_nodes())

"""Fix old DataNodes - set node_type='data_node' for records with NULL node_type."""
import asyncio
from sqlalchemy import text, select, update
from app.database import async_session_maker, engine


async def fix_old_datanodes():
    print("🔧 Fixing old DataNodes with NULL node_type...")
    
    async with async_session_maker() as db:
        # Check how many nodes have NULL node_type
        result = await db.execute(
            text("SELECT COUNT(*) FROM nodes WHERE node_type IS NULL")
        )
        null_count = result.scalar()
        print(f"Found {null_count} nodes with NULL node_type")
        
        if null_count == 0:
            print("✅ All nodes already have node_type set")
            return
        
        # Update nodes table - set node_type='data_node' for all data_nodes
        result = await db.execute(
            text("""
                UPDATE nodes 
                SET node_type = 'data_node'
                WHERE id IN (SELECT id FROM data_nodes)
                AND node_type IS NULL
            """)
        )
        await db.commit()
        
        updated = result.rowcount
        print(f"✅ Updated {updated} DataNodes with node_type='data_node'")
        
        # Verify
        result = await db.execute(
            text("SELECT COUNT(*) FROM nodes WHERE node_type IS NULL")
        )
        remaining_null = result.scalar()
        print(f"Remaining NULL node_type: {remaining_null}")


if __name__ == '__main__':
    asyncio.run(fix_old_datanodes())

"""Test cascade deletion at database level"""
import asyncio
from sqlalchemy import text
from app.database import async_session_maker

async def test_db_cascade():
    """Test that CASCADE on FK works at database level."""
    
    async with async_session_maker() as session:
        # Create a temporary test node directly in DB
        test_id = '00000000-0000-0000-0000-000000000001'
        
        print("\n🔧 Creating temporary test node...")
        
        # Insert into nodes table
        await session.execute(
            text("""
                INSERT INTO nodes (id, board_id, node_type, x, y, created_at, updated_at)
                SELECT :id, id, 'data_node', 0, 0, NOW(), NOW()
                FROM boards LIMIT 1
            """),
            {"id": test_id}
        )
        
        # Insert into data_nodes table
        await session.execute(
            text("""
                INSERT INTO data_nodes (id, name, description, data_source_type, data)
                VALUES (:id, 'Test Node', 'Test', 'sql_query', '{}')
            """),
            {"id": test_id}
        )
        
        await session.commit()
        print(f"✅ Test node created with ID: {test_id}")
        
        # Verify node exists in both tables
        base_count = await session.execute(
            text("SELECT COUNT(*) FROM nodes WHERE id = :id"),
            {"id": test_id}
        )
        data_count = await session.execute(
            text("SELECT COUNT(*) FROM data_nodes WHERE id = :id"),
            {"id": test_id}
        )
        
        print(f"\n📊 Before deletion:")
        print(f"   - nodes: {base_count.scalar()}")
        print(f"   - data_nodes: {data_count.scalar()}")
        
        # Delete ONLY from nodes table (CASCADE should delete from data_nodes)
        print(f"\n🗑️  Deleting from nodes table only...")
        await session.execute(
            text("DELETE FROM nodes WHERE id = :id"),
            {"id": test_id}
        )
        await session.commit()
        
        # Check if cascade deletion worked
        base_count_after = await session.execute(
            text("SELECT COUNT(*) FROM nodes WHERE id = :id"),
            {"id": test_id}
        )
        data_count_after = await session.execute(
            text("SELECT COUNT(*) FROM data_nodes WHERE id = :id"),
            {"id": test_id}
        )
        
        print(f"\n📊 After deletion from nodes:")
        print(f"   - nodes: {base_count_after.scalar()}")
        print(f"   - data_nodes: {data_count_after.scalar()}")
        
        if base_count_after.scalar() == 0 and data_count_after.scalar() == 0:
            print(f"\n✅ SUCCESS: CASCADE deletion works at DB level!")
            print(f"   Deleting from 'nodes' automatically deleted from 'data_nodes'")
        else:
            print(f"\n❌ FAILURE: CASCADE not working properly")

if __name__ == "__main__":
    asyncio.run(test_db_cascade())

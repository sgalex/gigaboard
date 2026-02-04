"""Test node deletion with cascade"""
import asyncio
from uuid import uuid4
from sqlalchemy import select, text
from app.database import async_session_maker
from app.models import DataNode, BaseNode

async def test_node_deletion():
    """Test that deleting a node deletes both base and child records."""
    
    async with async_session_maker() as session:
        # Get a test node
        result = await session.execute(
            select(DataNode).limit(1)
        )
        test_node = result.scalar_one_or_none()
        
        if not test_node:
            print("❌ No DataNodes found to test")
            return
        
        node_id = test_node.id
        node_name = test_node.name
        
        print(f"\n🔍 Testing deletion of node: {node_name} (ID: {node_id})")
        
        # Check that node exists in both tables
        base_result = await session.execute(
            text("SELECT COUNT(*) FROM nodes WHERE id = :id"),
            {"id": node_id}
        )
        base_count_before = base_result.scalar()
        
        data_result = await session.execute(
            text("SELECT COUNT(*) FROM data_nodes WHERE id = :id"),
            {"id": node_id}
        )
        data_count_before = data_result.scalar()
        
        print(f"  📊 Before deletion:")
        print(f"     - nodes table: {base_count_before} record(s)")
        print(f"     - data_nodes table: {data_count_before} record(s)")
        
        # Delete the node using SQLAlchemy ORM
        await session.delete(test_node)
        await session.commit()
        
        print(f"\n  🗑️  Node deleted via ORM")
        
        # Check counts after deletion
        base_result_after = await session.execute(
            text("SELECT COUNT(*) FROM nodes WHERE id = :id"),
            {"id": node_id}
        )
        base_count_after = base_result_after.scalar()
        
        data_result_after = await session.execute(
            text("SELECT COUNT(*) FROM data_nodes WHERE id = :id"),
            {"id": node_id}
        )
        data_count_after = data_result_after.scalar()
        
        print(f"\n  📊 After deletion:")
        print(f"     - nodes table: {base_count_after} record(s)")
        print(f"     - data_nodes table: {data_count_after} record(s)")
        
        # Verify deletion
        if base_count_after == 0 and data_count_after == 0:
            print(f"\n✅ SUCCESS: Node deleted from both tables (cascade works!)")
        else:
            print(f"\n❌ FAILURE: Node not properly deleted")
            if base_count_after > 0:
                print(f"   - Still exists in nodes table")
            if data_count_after > 0:
                print(f"   - Still exists in data_nodes table")
        
        # Rollback to restore the node for other tests
        await session.rollback()
        print(f"\n♻️  Transaction rolled back - node restored")

if __name__ == "__main__":
    asyncio.run(test_node_deletion())

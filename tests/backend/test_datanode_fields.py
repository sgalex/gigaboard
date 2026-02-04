"""Test creating DataNode with source_mode and file_type"""
import asyncio
from uuid import uuid4
from app.database import async_session_maker
from app.models import DataNode
from sqlalchemy import select

async def test_datanode_creation():
    """Test creating a DataNode with new fields."""
    
    async with async_session_maker() as session:
        # Get first board for testing
        result = await session.execute(select(DataNode).limit(1))
        existing_node = result.scalar_one_or_none()
        
        if existing_node:
            print("\n✅ Found existing DataNode:")
            print(f"  ID: {existing_node.id}")
            print(f"  Name: {existing_node.name}")
            print(f"  Source Mode: {existing_node.source_mode}")
            print(f"  File Type: {existing_node.file_type}")
            print(f"  Data Source Type: {existing_node.data_source_type}")
        else:
            print("\n❌ No DataNodes found in database")
        
        # Count all nodes
        count_result = await session.execute(select(DataNode))
        all_nodes = count_result.scalars().all()
        
        print(f"\nTotal DataNodes: {len(all_nodes)}")
        
        if all_nodes:
            print("\nAll DataNodes:")
            for node in all_nodes:
                print(f"  - {node.name} | source_mode={node.source_mode} | file_type={node.file_type}")

if __name__ == "__main__":
    asyncio.run(test_datanode_creation())

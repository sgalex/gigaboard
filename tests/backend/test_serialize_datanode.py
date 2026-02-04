"""Test serializing DataNode to Pydantic schema (like API does)."""
import asyncio
from sqlalchemy import select
from app.database import async_session_maker
from app.models import DataNode, Board
from app.schemas.data_node import DataNodeResponse
from uuid import UUID


async def test_serialize():
    board_id = UUID('56fa26c6-5c91-4d5d-a032-34cc534a94ec')
    user_id = UUID('e5dc48c5-c575-48ee-b423-9b0c38881744')
    
    print("🔍 Testing DataNode serialization to Pydantic schema...")
    
    try:
        async with async_session_maker() as db:
            # Fetch DataNode (same as API does)
            result = await db.execute(
                select(DataNode)
                .join(Board)
                .where(DataNode.board_id == board_id, Board.user_id == user_id)
                .order_by(DataNode.created_at)
            )
            nodes = result.scalars().all()
            
            print(f"✅ Fetched {len(nodes)} DataNodes")
            
            # Try to serialize each node
            for node in nodes:
                print(f"\n📦 Serializing node {node.id}...")
                print(f"   Type: {type(node).__name__}")
                print(f"   data_node_type: {node.data_node_type}")
                print(f"   Has node_type attr: {hasattr(node, 'node_type')}")
                if hasattr(node, 'node_type'):
                    print(f"   node_type value: {node.node_type}")
                
                # Try to create Pydantic response
                try:
                    response = DataNodeResponse.model_validate(node)
                    print(f"   ✅ Serialization successful!")
                    print(f"   Response data_node_type: {response.data_node_type}")
                    print(f"   Response node_type: {response.node_type}")
                except Exception as e:
                    print(f"   ❌ Serialization failed: {e}")
                    import traceback
                    traceback.print_exc()
                    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(test_serialize())

"""Test fetching DataNodes like the API does."""
import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import async_session_maker
from app.models import DataNode, Board
from uuid import UUID


async def test_fetch():
    board_id = UUID('56fa26c6-5c91-4d5d-a032-34cc534a94ec')
    user_id = UUID('e5dc48c5-c575-48ee-b423-9b0c38881744')
    
    print(f"🔍 Fetching DataNodes for board {board_id}...")
    
    try:
        async with async_session_maker() as db:
            result = await db.execute(
                select(DataNode)
                .join(Board)
                .where(DataNode.board_id == board_id, Board.user_id == user_id)
                .order_by(DataNode.created_at)
            )
            nodes = result.scalars().all()
            
            print(f"✅ Successfully fetched {len(nodes)} DataNodes:")
            for node in nodes:
                print(f"  - {node.id}: {node.name} (type={node.data_node_type})")
                
    except Exception as e:
        print(f"❌ Error fetching DataNodes:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    asyncio.run(test_fetch())

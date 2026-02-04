"""Test list_data_nodes with polymorphic loading."""
import asyncio
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import with_polymorphic
from app.database import get_db
from app.models import DataNode, DataNodeText, DataNodeFile, DataNodeAPI, Board

async def test_list():
    async for db in get_db():
        try:
            # Get first board
            result = await db.execute(select(Board).limit(1))
            board = result.scalar_one_or_none()
            
            if not board:
                print("❌ No boards found")
                return
            
            print(f"✅ Testing board: {board.id}")
            print(f"   User: {board.user_id}")
            
            # Try with_polymorphic
            poly = with_polymorphic(DataNode, [DataNodeText, DataNodeFile, DataNodeAPI])
            
            stmt = (
                select(poly)
                .join(Board, poly.board_id == Board.id)
                .where(poly.board_id == board.id, Board.user_id == board.user_id)
                .order_by(poly.created_at)
            )
            
            print(f"\n📝 Query: {stmt}")
            
            result = await db.execute(stmt)
            nodes = list(result.scalars().all())
            
            print(f"\n✅ Found {len(nodes)} DataNodes:")
            for node in nodes:
                print(f"   - {node.id}: {node.name} (type: {node.node_type}, data_node_type: {node.data_node_type})")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        break

if __name__ == "__main__":
    asyncio.run(test_list())

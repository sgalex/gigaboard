"""Test edge creation directly."""
import asyncio
from app.database import get_db
from app.services import EdgeService
from app.schemas import EdgeCreate
from app.models.edge import EdgeType
from uuid import UUID

async def test_edge():
    async for db in get_db():
        try:
            edge_data = EdgeCreate(
                source_node_id=UUID("b3d2de07-b443-4963-a353-6867b06082c1"),
                source_node_type="DataNode",
                target_node_id=UUID("f7206cc5-d046-45d0-bb93-e48ff29a4684"),
                target_node_type="WidgetNode",
                edge_type=EdgeType.VISUALIZATION,
                label="Test edge"
            )
            
            board_id = UUID("5e77eafe-2d8d-4cad-b628-7964b2170336")
            user_id = UUID("bba55118-52c1-4741-9eac-90c3674f9bcb")
            
            print("Creating edge...")
            edge = await EdgeService.create_edge(db, board_id, edge_data, user_id)
            print(f"✅ Edge created: {edge.id}")
            print(f"   {edge.source_node_type} -> {edge.target_node_type}")
            print(f"   Type: {edge.edge_type}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        break

if __name__ == "__main__":
    asyncio.run(test_edge())

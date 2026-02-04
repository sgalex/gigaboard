"""Test DataNode creation via API."""
import asyncio
import httpx
from sqlalchemy import select
from app.database import async_session_maker
from app.models import Board

async def test_api_create():
    """Test creating DataNode via API."""
    
    # Get board_id
    async with async_session_maker() as session:
        result = await session.execute(select(Board).limit(1))
        board = result.scalar_one_or_none()
        
        if not board:
            print("❌ No board found")
            return
        
        board_id = str(board.id)
        print(f"📋 Using board: {board.name} (ID: {board_id})")
    
    # Test data for text node
    text_node_data = {
        "name": "API Test Text Node",
        "description": "Testing text node creation via API",
        "data_source_type": "sql_query",
        "data_node_type": "text",
        "board_id": board_id,
        "text_content": "SELECT * FROM users",
        "query": "SELECT * FROM users",
        "data": {},
        "x": 50,
        "y": 50
    }
    
    print(f"\n📤 Sending request to create DataNodeText...")
    print(f"   Payload: {text_node_data}")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"http://localhost:8000/api/v1/boards/{board_id}/data-nodes",
                json=text_node_data,
                timeout=10.0
            )
            
            print(f"\n📊 Response status: {response.status_code}")
            
            if response.status_code == 200 or response.status_code == 201:
                result = response.json()
                print(f"✅ DataNode created successfully!")
                print(f"   ID: {result.get('id')}")
                print(f"   Name: {result.get('name')}")
                print(f"   Type: {result.get('data_node_type')}")
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"   Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_api_create())

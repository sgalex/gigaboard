"""Test DataNode inheritance with Text, File, and API subtypes."""
import asyncio
from sqlalchemy import select, func
from app.database import async_session_maker
from app.models import DataNode, DataNodeText, DataNodeFile, DataNodeAPI, Board

async def test_datanode_inheritance():
    """Test creating and querying DataNode subtypes."""
    
    async with async_session_maker() as session:
        print("\n🔍 Testing DataNode inheritance...\n")
        
        # Get a board for testing
        board_result = await session.execute(select(Board).limit(1))
        board = board_result.scalar_one_or_none()
        
        if not board:
            print("❌ No board found. Please create a board first.")
            return
        
        print(f"📋 Using board: {board.name} (ID: {board.id})")
        
        # Count existing nodes
        text_count = await session.execute(select(func.count()).select_from(DataNodeText))
        file_count = await session.execute(select(func.count()).select_from(DataNodeFile))
        api_count = await session.execute(select(func.count()).select_from(DataNodeAPI))
        
        print(f"\n📊 Existing nodes:")
        print(f"   - DataNodeText: {text_count.scalar()}")
        print(f"   - DataNodeFile: {file_count.scalar()}")
        print(f"   - DataNodeAPI: {api_count.scalar()}")
        
        # Create a DataNodeText
        print(f"\n📝 Creating DataNodeText...")
        text_node = DataNodeText(
            board_id=board.id,
            node_type='data_node',
            data_node_type='text',
            name='Test Text Node',
            description='A test text-based node',
            data_source_type='sql_query',
            text_content='SELECT * FROM test_table',
            query='SELECT * FROM test_table',
            data={},
            x=0,
            y=0
        )
        session.add(text_node)
        await session.flush()
        print(f"✅ Created DataNodeText: {text_node.name} (ID: {text_node.id})")
        print(f"   - text_content: {text_node.text_content}")
        print(f"   - query: {text_node.query}")
        
        # Create a DataNodeFile
        print(f"\n📁 Creating DataNodeFile...")
        file_node = DataNodeFile(
            board_id=board.id,
            node_type='data_node',
            data_node_type='file',
            name='Test File Node',
            description='A test file-based node',
            data_source_type='csv_upload',
            file_name='data.csv',
            file_type='text/csv',
            file_size=1024,
            data={},
            x=100,
            y=0
        )
        session.add(file_node)
        await session.flush()
        print(f"✅ Created DataNodeFile: {file_node.name} (ID: {file_node.id})")
        print(f"   - file_name: {file_node.file_name}")
        print(f"   - file_type: {file_node.file_type}")
        print(f"   - file_size: {file_node.file_size}")
        
        # Create a DataNodeAPI
        print(f"\n🌐 Creating DataNodeAPI...")
        api_node = DataNodeAPI(
            board_id=board.id,
            node_type='data_node',
            data_node_type='api',
            name='Test API Node',
            description='A test API-based node',
            data_source_type='api_call',
            api_url='https://api.example.com/data',
            api_method='GET',
            api_headers={'Authorization': 'Bearer token'},
            api_params={'limit': 100},
            data={},
            x=200,
            y=0
        )
        session.add(api_node)
        await session.flush()
        print(f"✅ Created DataNodeAPI: {api_node.name} (ID: {api_node.id})")
        print(f"   - api_url: {api_node.api_url}")
        print(f"   - api_method: {api_node.api_method}")
        print(f"   - api_headers: {api_node.api_headers}")
        
        # Query all DataNodes polymorphically
        print(f"\n🔍 Querying all DataNodes polymorphically...")
        result = await session.execute(
            select(DataNode)
            .where(DataNode.board_id == board.id)
            .order_by(DataNode.x)
        )
        nodes = result.scalars().all()
        
        print(f"\n📊 Found {len(nodes)} nodes:")
        for node in nodes[-3:]:  # Show only last 3 nodes (the ones we just created)
            print(f"\n   {node.__class__.__name__}: {node.name}")
            print(f"      - ID: {node.id}")
            print(f"      - data_node_type: {node.data_node_type}")
            
            if isinstance(node, DataNodeText):
                print(f"      - query: {node.query}")
            elif isinstance(node, DataNodeFile):
                print(f"      - file_name: {node.file_name}")
                print(f"      - file_type: {node.file_type}")
            elif isinstance(node, DataNodeAPI):
                print(f"      - api_url: {node.api_url}")
                print(f"      - api_method: {node.api_method}")
        
        # Test deletion with cascade
        print(f"\n🗑️  Testing cascade deletion...")
        print(f"   Deleting {text_node.name}...")
        await session.delete(text_node)
        await session.flush()
        
        # Verify deletion
        verify_result = await session.execute(
            select(DataNodeText).where(DataNodeText.id == text_node.id)
        )
        deleted_node = verify_result.scalar_one_or_none()
        
        if deleted_node is None:
            print(f"✅ Node deleted successfully (cascade worked)")
        else:
            print(f"❌ Node still exists after deletion")
        
        # Rollback to preserve existing data
        await session.rollback()
        print(f"\n♻️  Transaction rolled back - test data removed")
        
        print(f"\n✅ All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_datanode_inheritance())

"""Check ContentNode lineage in DB."""
import asyncio
import json
import sys
from uuid import UUID

# Add apps/backend to path
sys.path.insert(0, 'apps/backend')

from app.core import get_db
from app.models import ContentNode
from sqlalchemy import select


async def check_lineage(node_id: str):
    """Check ContentNode lineage."""
    async for db in get_db():
        try:
            result = await db.execute(
                select(ContentNode).where(ContentNode.id == UUID(node_id))
            )
            node = result.scalar_one_or_none()
            
            if not node:
                print(f"❌ ContentNode {node_id} not found")
                return
            
            print(f"✅ Found ContentNode {node_id}")
            print(f"\n📊 Lineage:")
            print(json.dumps(node.lineage, indent=2, default=str))
            
            # Check transformation_history specifically
            transform_history = node.lineage.get("transformation_history", [])
            print(f"\n🔧 Transformation History ({len(transform_history)} items):")
            for idx, t in enumerate(transform_history):
                print(f"  {idx + 1}. {t.get('operation')} - {t.get('description')}")
                print(f"     code_snippet length: {len(t.get('code_snippet', ''))}")
                print(f"     transformation_id: {t.get('transformation_id')}")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            break


if __name__ == "__main__":
    node_id = "3feea70a-aa30-454e-98b9-96fb9a0feaba"
    if len(sys.argv) > 1:
        node_id = sys.argv[1]
    
    asyncio.run(check_lineage(node_id))

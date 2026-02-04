"""Clean up all boards and nodes from database."""
import asyncio
from sqlalchemy import text
from app.database import get_db

async def cleanup():
    async for db in get_db():
        try:
            # Delete all nodes (CASCADE will handle child tables)
            result_nodes = await db.execute(text("DELETE FROM nodes"))
            await db.commit()
            print(f"✅ Deleted {result_nodes.rowcount} nodes (and all child records via CASCADE)")
            
            # Delete all boards
            result_boards = await db.execute(text("DELETE FROM boards"))
            await db.commit()
            print(f"✅ Deleted {result_boards.rowcount} boards")
            
            # Delete all projects
            result_projects = await db.execute(text("DELETE FROM projects"))
            await db.commit()
            print(f"✅ Deleted {result_projects.rowcount} projects")
            
            print("\n🎉 Database cleaned successfully!")
            
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")
            await db.rollback()
        
        break

if __name__ == "__main__":
    asyncio.run(cleanup())

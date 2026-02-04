"""Drop nodes table if exists"""
import asyncio
from sqlalchemy import text
from app.database import engine

async def drop_nodes_table():
    """Drop nodes table."""
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS nodes CASCADE"))
        print("✅ Table 'nodes' dropped successfully")

if __name__ == "__main__":
    asyncio.run(drop_nodes_table())

import asyncio
from app.database import engine
from sqlalchemy import text

async def check_tables():
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        ))
        tables = [row[0] for row in result]
        print("Tables in database:")
        for table in tables:
            print(f"  - {table}")

asyncio.run(check_tables())

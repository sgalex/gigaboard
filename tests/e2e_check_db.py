"""Quick DB check for E2E testing."""
import asyncio
import sys
sys.path.insert(0, "apps/backend")

from app.core.database import engine
from sqlalchemy import text


async def check():
    async with engine.connect() as conn:
        # List tables
        result = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        )
        tables = [r[0] for r in result.fetchall()]
        print("Tables:", tables)

        # Check users
        if "users" in tables:
            result = await conn.execute(
                text("SELECT id, email, username FROM users LIMIT 5")
            )
            users = result.fetchall()
            print(f"Users ({len(users)}):", users)

        # Check projects
        if "projects" in tables:
            result = await conn.execute(
                text("SELECT id, name FROM projects LIMIT 5")
            )
            projects = result.fetchall()
            print(f"Projects ({len(projects)}):", projects)

        # Check boards
        if "boards" in tables:
            result = await conn.execute(
                text("SELECT id, name FROM boards LIMIT 5")
            )
            boards = result.fetchall()
            print(f"Boards ({len(boards)}):", boards)

        # Check content_nodes columns
        if "content_nodes" in tables:
            result = await conn.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name='content_nodes'")
            )
            cols = [r[0] for r in result.fetchall()]
            print(f"ContentNode columns: {cols}")

            result = await conn.execute(
                text("SELECT id FROM content_nodes LIMIT 5")
            )
            nodes = result.fetchall()
            print(f"ContentNodes ({len(nodes)}):", nodes)


asyncio.run(check())

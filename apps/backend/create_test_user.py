"""Create test user and board directly in database."""
import asyncio
import uuid
import sys
import os
from pathlib import Path

# Setup path (same as test_real_multi_agent.py)
os.chdir(Path(__file__).parent)
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import async_session_maker
from app.services import AuthService
from app.schemas import UserCreate

# Import all models to ensure relationships are configured
from app.models import Board, User, Project
from app.models.agent_session import AgentSession
from sqlalchemy import select

async def create_test_user():
    async with async_session_maker() as db:
        try:
            # Create test user
            user_data = UserCreate(
                email="test@gigaboard.dev",
                password="testpass123",
                username="testuser"
            )
            
            user, token = await AuthService.register_user(db, user_data)
            
            print("✅ Test user created successfully!")
            print(f"📧 Email: {user.email}")
            print(f"👤 Username: {user.username}")
            print(f"🆔 User ID: {user.id}")
            
            # Create test board
            board = Board(
                id=uuid.uuid4(),
                name="Test Board for Multi-Agent Testing",
                user_id=user.id,
                description="Board created for integration tests"
            )
            db.add(board)
            await db.commit()
            await db.refresh(board)
            
            print("✅ Test board created successfully!")
            print(f"📋 Board Name: {board.name}")
            print(f"🆔 Board ID: {board.id}")
            
            print("\n" + "="*60)
            print("📝 Copy these IDs for test_real_multi_agent.py:")
            print("="*60)
            print(f"USER_ID = '{user.id}'")
            print(f"BOARD_ID = '{board.id}'")
            print("="*60)
            
        except ValueError as e:
            print(f"⚠️ User already exists: {e}")
            print("Getting existing user and board...")
            
            # Get existing user
            stmt = select(User).where(User.email == "test@gigaboard.dev")
            result = await db.execute(stmt)
            user = result.scalar_one_or_none()
            
            if user:
                print(f"✅ Found existing user")
                print(f"🆔 User ID: {user.id}")
                
                # Get or create project
                stmt = select(Project).where(Project.user_id == user.id)
                result = await db.execute(stmt)
                project = result.scalar_one_or_none()
                
                if not project:
                    project = Project(
                        id=uuid.uuid4(),
                        name="Test Project for Multi-Agent",
                        user_id=user.id,
                        description="Project created for integration tests"
                    )
                    db.add(project)
                    await db.commit()
                    await db.refresh(project)
                    print("✅ Created new project")
                else:
                    print(f"✅ Found existing project")
                
                print(f"🆔 Project ID: {project.id}")
                
                # Get or create board
                stmt = select(Board).where(Board.user_id == user.id)
                result = await db.execute(stmt)
                board = result.scalar_one_or_none()
                
                if not board:
                    board = Board(
                        id=uuid.uuid4(),
                        name="Test Board for Multi-Agent Testing",
                        project_id=project.id,
                        user_id=user.id,
                        description="Board created for integration tests"
                    )
                    db.add(board)
                    await db.commit()
                    await db.refresh(board)
                    print("✅ Created new board")
                else:
                    print(f"✅ Found existing board")
                
                print(f"🆔 Board ID: {board.id}")
                
                print("\n" + "="*60)
                print("📝 Copy these IDs for test_real_multi_agent.py:")
                print("="*60)
                print(f"USER_ID = '{user.id}'")
                print(f"BOARD_ID = '{board.id}'")
                print("="*60)
        
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(create_test_user())

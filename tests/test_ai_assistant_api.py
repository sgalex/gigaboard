"""
Тест AI Assistant endpoints.

Тестирует:
1. POST /api/v1/boards/{board_id}/ai/chat - отправка сообщения
2. GET /api/v1/boards/{board_id}/ai/chat/history - получение истории
3. DELETE /api/v1/boards/{board_id}/ai/chat/session/{session_id} - удаление сессии

Запуск:
    python -m tests.test_ai_assistant_api
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корень backend в PYTHONPATH
backend_root = Path(__file__).parent.parent / "apps" / "backend"
sys.path.insert(0, str(backend_root))

import httpx

BASE_URL = "http://localhost:8000"


async def get_auth_token():
    """Получить токен авторизации"""
    async with httpx.AsyncClient() as client:
        # Пытаемся войти
        response = await client.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "testpassword123"
            }
        )
        
        if response.status_code == 200:
            return response.json()["access_token"]
        
        # Проверим что не так с логином
        print(f"Login failed: {response.status_code}")
        print(f"Response: {response.text}")
        
        # Если не получилось - регистрируемся с новым email
        import random
        random_suffix = random.randint(1000, 9999)
        test_email = f"test{random_suffix}@example.com"
        test_username = f"testuser{random_suffix}"
        
        print(f"Creating new test user: {test_email}...")
        response = await client.post(
            f"{BASE_URL}/api/v1/auth/register",
            json={
                "email": test_email,
                "username": test_username,
                "password": "testpassword123"
            }
        )
        
        # Register может вернуть 200 или 201
        if response.status_code in [200, 201]:
            # Register уже возвращает токен
            return response.json()["access_token"]
        
        print(f"❌ Register response: {response.status_code}")
        print(f"Response body: {response.text}")
        raise Exception(f"Failed to get auth token: {response.status_code} - {response.text}")


async def test_ai_chat():
    """Тест отправки сообщения AI"""
    print("\n" + "="*60)
    print("Тест 1: Отправка сообщения AI")
    print("="*60)
    
    token = await get_auth_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # Сначала создадим тестовый проект и доску
    async with httpx.AsyncClient() as client:
        # Создать проект
        response = await client.post(
            f"{BASE_URL}/api/v1/projects",
            json={"name": "Test AI Project", "description": "For testing AI"},
            headers=headers
        )
        
        if response.status_code not in [200, 201]:
            print(f"❌ Failed to create project: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        project_id = response.json()["id"]
        print(f"✅ Created project: {project_id}")
        
        # Создать доску
        response = await client.post(
            f"{BASE_URL}/api/v1/boards",
            json={"name": "Test AI Board", "description": "Testing AI chat", "project_id": project_id},
            headers=headers
        )
        
        if response.status_code not in [200, 201]:
            print(f"❌ Failed to create board: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        board_id = response.json()["id"]
        print(f"✅ Created board: {board_id}")
        
        # Отправить сообщение AI
        print("\n📤 Sending message to AI...")
        response = await client.post(
            f"{BASE_URL}/api/v1/boards/{board_id}/ai/chat",
            json={
                "message": "Привет! Что ты можешь мне рассказать об этой доске?"
            },
            headers=headers
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to send message: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        data = response.json()
        session_id = data["session_id"]
        
        print("\n📥 AI Response:")
        print("-" * 60)
        print(data["response"])
        print("-" * 60)
        print(f"✅ Session ID: {session_id}")
        
        if data.get("suggested_actions"):
            print(f"💡 Suggested actions: {len(data['suggested_actions'])}")
        
        return True, board_id, session_id


async def test_chat_history(board_id, session_id, token):
    """Тест получения истории чата"""
    print("\n" + "="*60)
    print("Тест 2: Получение истории чата")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/api/v1/boards/{board_id}/ai/chat/history",
            params={"session_id": session_id},
            headers=headers
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to get history: {response.status_code}")
            return False
        
        data = response.json()
        messages = data["messages"]
        
        print(f"\n📜 Chat History ({len(messages)} messages):")
        print("-" * 60)
        
        for msg in messages:
            role = msg["role"].upper()
            content = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
            print(f"[{role}] {content}")
        
        print("-" * 60)
        print(f"✅ Retrieved {len(messages)} messages")
        
        return True


async def test_delete_session(board_id, session_id, token):
    """Тест удаления сессии"""
    print("\n" + "="*60)
    print("Тест 3: Удаление сессии чата")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"{BASE_URL}/api/v1/boards/{board_id}/ai/chat/session/{session_id}",
            headers=headers
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to delete session: {response.status_code}")
            return False
        
        data = response.json()
        deleted_count = data["deleted_messages"]
        
        print(f"🗑️  Deleted {deleted_count} messages")
        print(f"✅ Session cleared: {session_id}")
        
        return True


async def main():
    """Запуск всех тестов"""
    print("\n" + "🚀 " * 20)
    print("GigaBoard - AI Assistant API Tests")
    print("🚀 " * 20)
    print(f"\nBase URL: {BASE_URL}")
    print("\n⚠️  Убедитесь, что backend запущен (run-backend.ps1)")
    
    try:
        # Получить токен
        print("\n🔐 Authenticating...")
        token = await get_auth_token()
        print("✅ Authentication successful")
        
        # Тест 1: Отправка сообщения
        result = await test_ai_chat()
        if isinstance(result, tuple):
            success, board_id, session_id = result
            if not success:
                print("\n❌ Test 1 failed")
                return
        else:
            print("\n❌ Test 1 failed")
            return
        
        # Тест 2: История чата
        if not await test_chat_history(board_id, session_id, token):
            print("\n❌ Test 2 failed")
            return
        
        # Тест 3: Удаление сессии
        if not await test_delete_session(board_id, session_id, token):
            print("\n❌ Test 3 failed")
            return
        
        print("\n" + "="*60)
        print("🎉 Все тесты успешно пройдены!")
        print("✅ AI Assistant API работает корректно")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

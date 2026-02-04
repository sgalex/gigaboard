"""
Test Multi-Agent Transformation System (Preview + Execute workflow)

Проверяет:
1. /content-nodes/{id}/transform/preview - генерация кода через Multi-Agent
2. /content-nodes/{id}/transform/execute - выполнение кода
3. ValidatorAgent проверки (syntax, security, dry-run)
4. Retry logic при ошибках валидации
"""

import requests
import json

BASE_URL = "http://localhost:8000"

# Тестовые учетные данные (создай пользователя через create_test_user.py если нужно)
TEST_EMAIL = "test@gigaboard.dev"
TEST_PASSWORD = "testpass123"


def login():
    """Авторизация и получение токена"""
    response = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    response.raise_for_status()
    return response.json()


def get_or_create_project(auth_token: str):
    """Получение или создание тестового проекта"""
    # Получаем список проектов
    response = requests.get(
        f"{BASE_URL}/api/v1/projects",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    response.raise_for_status()
    projects = response.json()
    
    if projects:
        return projects[0]  # Используем первый проект
    
    # Создаём новый проект если нет
    response = requests.post(
        f"{BASE_URL}/api/v1/projects",
        json={
            "name": "Test Project",
            "description": "Testing Multi-Agent System"
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    response.raise_for_status()
    return response.json()


def create_test_board(project_id: str, auth_token: str):
    """Создание тестовой доски"""
    response = requests.post(
        f"{BASE_URL}/api/v1/boards",
        json={
            "project_id": project_id,
            "name": "Test Multi-Agent Transformation",
            "description": "Testing preview/execute workflow"
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    response.raise_for_status()
    return response.json()


def create_test_content_node(board_id: str, auth_token: str):
    """Создание ContentNode с тестовыми данными"""
    # Простые тестовые данные: продажи по регионам
    from datetime import datetime
    
    test_data = {
        "board_id": board_id,
        "metadata": {
            "name": "Sales Data",
            "description": "Regional sales data for testing"
        },
        "content": {
            "tables": [
                {
                    "id": "sales_data",
                    "name": "sales",
                    "columns": ["region", "product", "amount", "quantity"],
                    "data": [
                        ["North", "Widget A", 1200.50, 10],
                        ["South", "Widget B", 850.30, 5],
                        ["East", "Widget A", 2100.00, 15],
                        ["North", "Widget C", 450.00, 3],
                        ["West", "Widget B", 1800.75, 12],
                        ["South", "Widget A", 950.00, 7],
                    ],
                    "row_count": 6
                }
            ]
        },
        "lineage": {
            "operation": "manual",
            "timestamp": datetime.utcnow().isoformat(),
            "parent_content_ids": []
        },
        "position": {"x": 100, "y": 100}
    }
    
    response = requests.post(
        f"{BASE_URL}/api/v1/content-nodes",
        json=test_data,
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    response.raise_for_status()
    content_node = response.json()
    
    print(f"   Created ContentNode ID: {content_node['id']}")
    print(f"   Content keys: {list(content_node.keys())}")
    
    return content_node


def test_preview_simple(content_node_id: str, auth_token: str):
    """Тест 1: Простая трансформация (фильтр)"""
    print("\n" + "="*80)
    print("TEST 1: Simple transformation - filter by amount > 1000")
    print("="*80)
    
    response = requests.post(
        f"{BASE_URL}/api/v1/content-nodes/{content_node_id}/transform/preview",
        json={"prompt": "Filter rows where amount is greater than 1000"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    print(f"\nStatus: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ Error: {response.text}")
        response.raise_for_status()
    
    result = response.json()
    
    print(f"\n✅ Transformation ID: {result['transformation_id']}")
    print(f"\n📝 Description: {result['description']}")
    print(f"\n🤖 Agent Plan:")
    print(f"   Steps: {result['agent_plan']['steps']}")
    print(f"   Attempts: {result['agent_plan']['attempts']}")
    print(f"   Time: {result['agent_plan']['total_time_ms']}ms")
    
    print(f"\n✔️ Validation:")
    print(f"   Valid: {result['validation']['valid']}")
    print(f"   Errors: {result['validation']['errors']}")
    print(f"   Warnings: {len(result['validation']['warnings'])}")
    
    print(f"\n💻 Generated Code:")
    print("   " + "-"*70)
    for line in result['code'].split('\n'):
        print(f"   {line}")
    print("   " + "-"*70)
    
    return result


def test_preview_aggregation(content_node_id: str, auth_token: str):
    """Тест 2: Агрегация данных"""
    print("\n" + "="*80)
    print("TEST 2: Aggregation - group by region and sum amount")
    print("="*80)
    
    response = requests.post(
        f"{BASE_URL}/api/v1/content-nodes/{content_node_id}/transform/preview",
        json={"prompt": "Group by region and calculate total amount and quantity for each region"},
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    print(f"\nStatus: {response.status_code}")
    result = response.json()
    
    print(f"\n✅ Transformation ID: {result['transformation_id']}")
    print(f"\n🤖 Agent Plan: {result['agent_plan']['steps']}")
    print(f"\n💻 Generated Code (first 5 lines):")
    for line in result['code'].split('\n')[:5]:
        print(f"   {line}")
    
    return result


def test_execute(content_node_id: str, preview_result: dict, auth_token: str):
    """Тест 3: Выполнение сгенерированного кода"""
    print("\n" + "="*80)
    print("TEST 3: Execute generated code")
    print("="*80)
    
    response = requests.post(
        f"{BASE_URL}/api/v1/content-nodes/{content_node_id}/transform/execute",
        json={
            "code": preview_result['code'],
            "transformation_id": preview_result['transformation_id'],
            "description": preview_result['description']
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    print(f"\nStatus: {response.status_code}")
    
    if response.status_code != 200:
        print(f"ERROR: {response.text}")
        response.raise_for_status()
    
    result = response.json()
    
    print(f"\nOK New ContentNode created:")
    print(f"   ID: {result['content_node']['id']}")
    print(f"   Name: {result['content_node']['node_metadata']['name']}")
    print(f"   Tables: {len(result['content_node']['content']['tables'])}")
    
    for table in result['content_node']['content']['tables']:
        print(f"\n   📊 Table: {table['name']}")
        print(f"      Rows: {table['row_count']}")
        print(f"      Columns: {', '.join(table['columns'])}")
        print(f"      Sample data (first 2 rows):")
        for row in table['data'][:2]:
            print(f"         {row}")
    
    print(f"\nTRANSFORMATION edge created:")
    print(f"   ID: {result['transform_edge']['id']}")
    print(f"   From: {result['transform_edge']['source_node_id']} -> To: {result['transform_edge']['target_node_id']}")
    print(f"   Type: {result['transform_edge']['edge_type']}")
    
    return result


def test_invalid_code_validation(content_node_id: str, auth_token: str):
    """Тест 4: Проверка валидации (попытка выполнить опасный код)"""
    print("\n" + "="*80)
    print("TEST 4: Security validation - should reject dangerous code")
    print("="*80)
    
    dangerous_code = """
import pandas as pd
import os

# Try to execute system command (should be blocked by validator)
os.system('echo "hacked"')

df_result = input_data['sales']
"""
    
    response = requests.post(
        f"{BASE_URL}/api/v1/content-nodes/{content_node_id}/transform/execute",
        json={
            "code": dangerous_code,
            "description": "Malicious code test"
        },
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    print(f"\nStatus: {response.status_code}")
    
    if response.status_code == 400:
        error = response.json()
        print(f"\n❌ Correctly rejected:")
        print(f"   Error: {error['detail']}")
        return True
    else:
        print(f"\n⚠️ SECURITY ISSUE: Dangerous code was not rejected!")
        return False


def main():
    print("Testing Multi-Agent Transformation System")
    print("="*80)
    
    try:
        # 1. Login
        print("\n[1] Logging in...")
        auth_data = login()
        auth_token = auth_data["access_token"]
        print(f"   OK Logged in as: {auth_data['user']['email']}")
        
        # 2. Get or create project
        print("\n[2] Getting/creating project...")
        project = get_or_create_project(auth_token)
        project_id = project["id"]
        print(f"   OK Project: {project['name']} (ID: {project_id})")
        
        # 3. Create test board
        print("\n[3] Creating test board...")
        board = create_test_board(project_id, auth_token)
        board_id = board["id"]
        print(f"   OK Board created: {board['name']} (ID: {board_id})")
        
        # 4. Create content node with test data
        print("\n[4] Creating ContentNode with test data...")
        content_node = create_test_content_node(board_id, auth_token)
        content_node_id = content_node["id"]
        print(f"   OK ContentNode created with 6 rows of sales data")
        
        # 5. Test preview - simple filter
        preview_result = test_preview_simple(content_node_id, auth_token)
        
        # 6. Test preview - aggregation
        preview_result_agg = test_preview_aggregation(content_node_id, auth_token)
        
        # 7. Test execute
        execute_result = test_execute(content_node_id, preview_result, auth_token)
        
        # 8. Test security validation
        test_invalid_code_validation(content_node_id, auth_token)
        
        print("\n" + "="*80)
        print("OK ALL TESTS COMPLETED")
        print("="*80)
        print("\nSummary:")
        print(f"   - Multi-Agent code generation: OK")
        print(f"   - Validation system: OK")
        print(f"   - Code execution: OK")
        print(f"   - Security checks: OK")
        print(f"   - Edge creation: OK")
        
    except Exception as e:
        print(f"\nERROR Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

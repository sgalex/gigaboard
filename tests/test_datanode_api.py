"""Test script for DataNode architecture API endpoints."""
import requests
import json
from uuid import uuid4

BASE_URL = "http://localhost:8000/api/v1"

# Test credentials (assuming you have a test user)
# You'll need to replace these with actual credentials or create a test user first
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpass123"

def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def print_result(operation, status_code, response):
    """Print operation result."""
    status_icon = "✅" if 200 <= status_code < 300 else "❌"
    print(f"{status_icon} {operation}: {status_code}")
    if isinstance(response, dict):
        print(json.dumps(response, indent=2, default=str))
    else:
        print(response)
    print()

# Step 1: Login to get token
print_section("1. Authentication")
auth_response = requests.post(
    f"{BASE_URL}/auth/login",
    json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
)
print_result("Login", auth_response.status_code, auth_response.json() if auth_response.ok else auth_response.text)

if not auth_response.ok:
    print("❌ Authentication failed. Please create a test user first.")
    print(f"Run: POST {BASE_URL}/auth/register")
    print(f'Body: {{"email": "{TEST_EMAIL}", "password": "{TEST_PASSWORD}", "username": "testuser"}}')
    exit(1)

token = auth_response.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}

# Step 2: Create a project
print_section("2. Create Project")
project_response = requests.post(
    f"{BASE_URL}/projects",
    headers=headers,
    json={
        "name": "Test Project - DataNode Architecture",
        "description": "Testing new DataNode, WidgetNode, CommentNode endpoints"
    }
)
print_result("Create Project", project_response.status_code, project_response.json() if project_response.ok else project_response.text)

if not project_response.ok:
    exit(1)

project_id = project_response.json().get("id")

# Step 3: Create a board
print_section("3. Create Board")
board_response = requests.post(
    f"{BASE_URL}/boards",
    headers=headers,
    json={
        "name": "Test Board - Nodes",
        "description": "Testing DataNode architecture",
        "project_id": project_id
    }
)
print_result("Create Board", board_response.status_code, board_response.json() if board_response.ok else board_response.text)

if not board_response.ok:
    exit(1)

board_id = board_response.json().get("id")

# Step 4: Create DataNode (SQL Query)
print_section("4. Create DataNode (SQL Query)")
data_node_response = requests.post(
    f"{BASE_URL}/boards/{board_id}/data-nodes",
    headers=headers,
    json={
        "name": "Sales Data",
        "data_source_type": "SQL_QUERY",
        "query": "SELECT * FROM sales WHERE date >= '2026-01-01'",
        "x": 100,
        "y": 100,
        "schema": {
            "columns": ["id", "date", "amount", "customer"],
            "types": ["int", "date", "decimal", "string"]
        }
    }
)
print_result("Create DataNode", data_node_response.status_code, data_node_response.json() if data_node_response.ok else data_node_response.text)

data_node_id = data_node_response.json().get("id") if data_node_response.ok else None

# Step 5: Create another DataNode (API Call)
print_section("5. Create DataNode (API Call)")
data_node_2_response = requests.post(
    f"{BASE_URL}/boards/{board_id}/data-nodes",
    headers=headers,
    json={
        "name": "Weather API",
        "data_source_type": "API_CALL",
        "api_config": {
            "url": "https://api.weather.com/forecast",
            "method": "GET",
            "headers": {"API-Key": "test123"}
        },
        "x": 400,
        "y": 100
    }
)
print_result("Create DataNode (API)", data_node_2_response.status_code, data_node_2_response.json() if data_node_2_response.ok else data_node_2_response.text)

data_node_2_id = data_node_2_response.json().get("id") if data_node_2_response.ok else None

# Step 6: Create WidgetNode (Visualization)
print_section("6. Create WidgetNode")
widget_node_response = requests.post(
    f"{BASE_URL}/boards/{board_id}/widget-nodes",
    headers=headers,
    json={
        "name": "Sales Chart",
        "description": "Bar chart showing sales by month",
        "html_code": "<div id='chart'></div>",
        "css_code": "#chart { width: 100%; height: 400px; }",
        "js_code": "// Chart.js code here",
        "x": 700,
        "y": 100,
        "width": 400,
        "height": 300
    }
)
print_result("Create WidgetNode", widget_node_response.status_code, widget_node_response.json() if widget_node_response.ok else widget_node_response.text)

widget_node_id = widget_node_response.json().get("id") if widget_node_response.ok else None

# Step 7: Create CommentNode
print_section("7. Create CommentNode")
comment_node_response = requests.post(
    f"{BASE_URL}/boards/{board_id}/comment-nodes",
    headers=headers,
    json={
        "content": "This data looks good! But we need to add filtering.",
        "x": 100,
        "y": 400,
        "color": "#FFC107"
    }
)
print_result("Create CommentNode", comment_node_response.status_code, comment_node_response.json() if comment_node_response.ok else comment_node_response.text)

comment_node_id = comment_node_response.json().get("id") if comment_node_response.ok else None

# Step 8: Create Edges
if data_node_id and data_node_2_id:
    print_section("8. Create TRANSFORMATION Edge (DataNode -> DataNode)")
    edge_1_response = requests.post(
        f"{BASE_URL}/boards/{board_id}/edges",
        headers=headers,
        json={
            "source_node_id": data_node_id,
            "source_node_type": "DataNode",
            "target_node_id": data_node_2_id,
            "target_node_type": "DataNode",
            "edge_type": "TRANSFORMATION",
            "transformation_code": "df_target = df_source.groupby('customer').sum()",
            "label": "Aggregate by customer"
        }
    )
    print_result("Create TRANSFORMATION Edge", edge_1_response.status_code, edge_1_response.json() if edge_1_response.ok else edge_1_response.text)

if data_node_id and widget_node_id:
    print_section("9. Create VISUALIZATION Edge (DataNode -> WidgetNode)")
    edge_2_response = requests.post(
        f"{BASE_URL}/boards/{board_id}/edges",
        headers=headers,
        json={
            "source_node_id": data_node_id,
            "source_node_type": "DataNode",
            "target_node_id": widget_node_id,
            "target_node_type": "WidgetNode",
            "edge_type": "VISUALIZATION",
            "label": "Display sales chart"
        }
    )
    print_result("Create VISUALIZATION Edge", edge_2_response.status_code, edge_2_response.json() if edge_2_response.ok else edge_2_response.text)

if comment_node_id and data_node_id:
    print_section("10. Create COMMENT Edge (CommentNode -> DataNode)")
    edge_3_response = requests.post(
        f"{BASE_URL}/boards/{board_id}/edges",
        headers=headers,
        json={
            "source_node_id": comment_node_id,
            "source_node_type": "CommentNode",
            "target_node_id": data_node_id,
            "target_node_type": "DataNode",
            "edge_type": "COMMENT",
            "label": "Comment on data quality"
        }
    )
    print_result("Create COMMENT Edge", edge_3_response.status_code, edge_3_response.json() if edge_3_response.ok else edge_3_response.text)

# Step 11: List all nodes
print_section("11. List All Nodes")
data_nodes = requests.get(f"{BASE_URL}/boards/{board_id}/data-nodes", headers=headers)
print_result("List DataNodes", data_nodes.status_code, data_nodes.json() if data_nodes.ok else data_nodes.text)

widget_nodes = requests.get(f"{BASE_URL}/boards/{board_id}/widget-nodes", headers=headers)
print_result("List WidgetNodes", widget_nodes.status_code, widget_nodes.json() if widget_nodes.ok else widget_nodes.text)

comment_nodes = requests.get(f"{BASE_URL}/boards/{board_id}/comment-nodes", headers=headers)
print_result("List CommentNodes", comment_nodes.status_code, comment_nodes.json() if comment_nodes.ok else comment_nodes.text)

edges = requests.get(f"{BASE_URL}/boards/{board_id}/edges", headers=headers)
print_result("List Edges", edges.status_code, edges.json() if edges.ok else edges.text)

# Step 12: Test board list with node counts
print_section("12. List Boards with Node Counts")
boards = requests.get(f"{BASE_URL}/boards", headers=headers)
print_result("List Boards", boards.status_code, boards.json() if boards.ok else boards.text)

print_section("✅ Testing Complete!")
print(f"Board ID: {board_id}")
print(f"DataNode ID: {data_node_id}")
print(f"WidgetNode ID: {widget_node_id}")
print(f"CommentNode ID: {comment_node_id}")

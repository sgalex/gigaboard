"""Quick API test using curl commands."""
import subprocess
import json
import sys

BASE_URL = "http://localhost:8000/api/v1"

def run_curl(method, url, data=None, token=None):
    """Run curl command and return response."""
    cmd = ["curl", "-X", method, url, "-H", "Content-Type: application/json"]
    
    if token:
        cmd.extend(["-H", f"Authorization: Bearer {token}"])
    
    if data:
        cmd.extend(["-d", json.dumps(data)])
    
    cmd.append("-s")  # Silent mode
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return json.loads(result.stdout) if result.stdout else None
    except Exception as e:
        print(f"Error: {e}")
        return None

print("🧪 DataNode Architecture API Tests\n")

# 1. Register test user
print("1️⃣ Registering test user...")
register_data = {
    "email": "test@gigaboard.dev",
    "password": "testpass123",
    "username": "testuser"
}
register_response = run_curl("POST", f"{BASE_URL}/auth/register", register_data)
if register_response and "access_token" in register_response:
    print("✅ User registered successfully")
    token = register_response["access_token"]
else:
    # Try login instead
    print("⚠️ Registration failed, trying login...")
    login_response = run_curl("POST", f"{BASE_URL}/auth/login", {
        "email": "test@gigaboard.dev",
        "password": "testpass123"
    })
    if login_response and "access_token" in login_response:
        print("✅ Login successful")
        token = login_response["access_token"]
    else:
        print("❌ Authentication failed")
        print(login_response)
        sys.exit(1)

# 2. Create project
print("\n2️⃣ Creating project...")
project_data = {
    "name": "DataNode Test Project",
    "description": "Testing new architecture"
}
project = run_curl("POST", f"{BASE_URL}/projects", project_data, token)
if project and "id" in project:
    print(f"✅ Project created: {project['name']} ({project['id']})")
    project_id = project["id"]
else:
    print("❌ Failed to create project")
    print(project)
    sys.exit(1)

# 3. Create board
print("\n3️⃣ Creating board...")
board_data = {
    "name": "Test Board",
    "description": "Testing DataNode, WidgetNode, CommentNode",
    "project_id": project_id
}
board = run_curl("POST", f"{BASE_URL}/boards", board_data, token)
if board and "id" in board:
    print(f"✅ Board created: {board['name']} ({board['id']})")
    board_id = board["id"]
else:
    print("❌ Failed to create board")
    print(board)
    sys.exit(1)

# 4. Create DataNode
print("\n4️⃣ Creating DataNode...")
data_node_data = {
    "name": "Sales Data",
    "data_source_type": "SQL_QUERY",
    "query": "SELECT * FROM sales",
    "x": 100,
    "y": 100
}
data_node = run_curl("POST", f"{BASE_URL}/boards/{board_id}/data-nodes", data_node_data, token)
if data_node and "id" in data_node:
    print(f"✅ DataNode created: {data_node['name']} ({data_node['id']})")
    data_node_id = data_node["id"]
else:
    print("❌ Failed to create DataNode")
    print(data_node)
    data_node_id = None

# 5. Create WidgetNode
print("\n5️⃣ Creating WidgetNode...")
widget_node_data = {
    "name": "Sales Chart",
    "description": "Bar chart of sales",
    "html_code": "<div id='chart'></div>",
    "css_code": "#chart { width: 100%; }",
    "js_code": "console.log('chart');",
    "x": 500,
    "y": 100,
    "width": 400,
    "height": 300
}
widget_node = run_curl("POST", f"{BASE_URL}/boards/{board_id}/widget-nodes", widget_node_data, token)
if widget_node and "id" in widget_node:
    print(f"✅ WidgetNode created: {widget_node['name']} ({widget_node['id']})")
    widget_node_id = widget_node["id"]
else:
    print("❌ Failed to create WidgetNode")
    print(widget_node)
    widget_node_id = None

# 6. Create CommentNode
print("\n6️⃣ Creating CommentNode...")
comment_node_data = {
    "content": "Great visualization! 👍",
    "x": 100,
    "y": 400,
    "color": "#4CAF50"
}
comment_node = run_curl("POST", f"{BASE_URL}/boards/{board_id}/comment-nodes", comment_node_data, token)
if comment_node and "id" in comment_node:
    print(f"✅ CommentNode created ({comment_node['id']})")
    comment_node_id = comment_node["id"]
else:
    print("❌ Failed to create CommentNode")
    print(comment_node)
    comment_node_id = None

# 7. Create VISUALIZATION Edge
if data_node_id and widget_node_id:
    print("\n7️⃣ Creating VISUALIZATION edge...")
    edge_data = {
        "source_node_id": data_node_id,
        "source_node_type": "DataNode",
        "target_node_id": widget_node_id,
        "target_node_type": "WidgetNode",
        "edge_type": "VISUALIZATION",
        "label": "Visualize sales"
    }
    edge = run_curl("POST", f"{BASE_URL}/boards/{board_id}/edges", edge_data, token)
    if edge and "id" in edge:
        print(f"✅ VISUALIZATION edge created ({edge['id']})")
    else:
        print("❌ Failed to create edge")
        print(edge)

# 8. List boards with node counts
print("\n8️⃣ Listing boards with node counts...")
boards = run_curl("GET", f"{BASE_URL}/boards", token=token)
if boards and isinstance(boards, list):
    for b in boards:
        if b.get("id") == board_id:
            print(f"✅ Board: {b['name']}")
            print(f"   - DataNodes: {b.get('data_nodes_count', 0)}")
            print(f"   - WidgetNodes: {b.get('widget_nodes_count', 0)}")
            print(f"   - CommentNodes: {b.get('comment_nodes_count', 0)}")
else:
    print("❌ Failed to list boards")
    print(boards)

print("\n✅ All tests completed!")
print(f"\n📋 Test Board URL: http://localhost:3000/boards/{board_id}")

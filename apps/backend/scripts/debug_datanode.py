"""Debug DataNode creation issue."""
import subprocess
import json

BASE_URL = "http://localhost:8000/api/v1"

# Login
print("1. Login...")
login_result = subprocess.run(
    ["curl", "-s", "-X", "POST", f"{BASE_URL}/auth/login",
     "-H", "Content-Type: application/json",
     "-d", json.dumps({"email": "test@gigaboard.dev", "password": "testpass123"})],
    capture_output=True,
    text=True
)
login_data = json.loads(login_result.stdout)
token = login_data["access_token"]
print(f"✅ Token: {token[:20]}...")

# Get first board
print("\n2. Get boards...")
boards_result = subprocess.run(
    ["curl", "-s", "-X", "GET", f"{BASE_URL}/boards",
     "-H", f"Authorization: Bearer {token}"],
    capture_output=True,
    text=True
)
boards = json.loads(boards_result.stdout)
board_id = boards[0]["id"]
print(f"✅ Board ID: {board_id}")

# Try to create DataNode with verbose output
print("\n3. Creating DataNode...")
data_node_data = {
    "name": "Test Data",
    "data_source_type": "SQL_QUERY",
    "query": "SELECT * FROM test",
    "x": 100,
    "y": 100
}

result = subprocess.run(
    ["curl", "-v", "-X", "POST", f"{BASE_URL}/boards/{board_id}/data-nodes",
     "-H", "Content-Type: application/json",
     "-H", f"Authorization: Bearer {token}",
     "-d", json.dumps(data_node_data)],
    capture_output=True,
    text=True
)

print("STDERR (headers):")
print(result.stderr)
print("\nSTDOUT (response body):")
print(result.stdout)

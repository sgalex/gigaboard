"""Test actual HTTP request to backend."""
import requests
import json

# Backend URL
BASE_URL = "http://localhost:8000"
BOARD_ID = "56fa26c6-5c91-4d5d-a032-34cc534a94ec"

# Test payload
payload = {
    "name": "тест",
    "data_source_type": "sql_query", 
    "data_node_type": "text",
    "x": 100,
    "y": 100,
    "data": {"content": "test content", "needs_ai_processing": True},
    "text_content": "test content"
}

print("Sending POST request to backend...")
print(f"URL: {BASE_URL}/api/v1/boards/{BOARD_ID}/data-nodes")
print(f"Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
print()

try:
    response = requests.post(
        f"{BASE_URL}/api/v1/boards/{BOARD_ID}/data-nodes",
        json=payload,
        timeout=5
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 422:
        print("\n❌ Validation Error Details:")
        detail = response.json().get('detail', [])
        for error in detail:
            print(f"  Location: {error.get('loc')}")
            print(f"  Message: {error.get('msg')}")
            print(f"  Type: {error.get('type')}")
            print()
            
except requests.exceptions.ConnectionError:
    print("❌ Could not connect to backend. Is it running?")
except Exception as e:
    print(f"❌ Error: {e}")

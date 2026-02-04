"""Test HTTP request to DataNodes API endpoint."""
import requests
import json

# Get token from test user
board_id = '56fa26c6-5c91-4d5d-a032-34cc534a94ec'
token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlNWRjNDhjNS1jNTc1LTQ4ZWUtYjQyMy05YjBjMzg4ODE3NDQiLCJleHAiOjE3Mzc5MjI4MDB9.pZ7mQn9v1DQ_example'  # Example token

url = f'http://localhost:8000/api/v1/boards/{board_id}/data-nodes'

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

print(f"🔍 GET {url}")
print(f"Headers: {headers}")

try:
    response = requests.get(url, headers=headers)
    print(f"\n📡 Response Status: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"\nResponse Body:")
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)
except Exception as e:
    print(f"❌ Error: {e}")

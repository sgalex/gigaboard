import requests

try:
    r = requests.get('http://localhost:8000/socket.io/?EIO=4&transport=polling')
    print(f'Status: {r.status_code}')
    print(f'Content-Type: {r.headers.get("Content-Type")}')
    print(f'Body: {r.text[:500] if r.text else "empty"}')
except Exception as e:
    print(f'Error: {e}')

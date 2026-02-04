import requests

headers = {
    "Origin": "http://localhost:5173",
    "Accept": "*/*",
}

try:
    r = requests.get('http://localhost:8000/socket.io/?EIO=4&transport=polling', headers=headers)
    print(f'Status: {r.status_code}')
    print(f'Headers: {dict(r.headers)}')
    print(f'Body: {r.text[:500] if r.text else "empty"}')
except Exception as e:
    print(f'Error: {e}')

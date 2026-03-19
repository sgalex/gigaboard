import json
import uuid

import httpx


BASE = "http://127.0.0.1:8000"
DASHBOARD_ID = "a913abbf-f301-4029-afca-544a3df81192"
EMAIL = "sgalex78@gmail.com"
PASSWORD = "Gytdvjnjrcbrjp28!"


def main() -> None:
    session_id = str(uuid.uuid4())
    login = httpx.post(
        f"{BASE}/api/v1/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=120,
    )
    login.raise_for_status()
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    first = httpx.post(
        f"{BASE}/api/v1/dashboards/{DASHBOARD_ID}/ai/chat",
        headers=headers,
        json={
            "message": "My name is ZedName123. Remember it.",
            "session_id": session_id,
            "context": {"allow_auto_filter": False},
        },
        timeout=300,
    )
    second = httpx.post(
        f"{BASE}/api/v1/dashboards/{DASHBOARD_ID}/ai/chat",
        headers=headers,
        json={
            "message": "What is my name?",
            "session_id": session_id,
            "context": {"allow_auto_filter": False},
        },
        timeout=300,
    )

    out = {
        "session_id": session_id,
        "first_status": first.status_code,
        "first_json": first.json(),
        "second_status": second.status_code,
        "second_json": second.json(),
    }
    with open("logs/dashboard_chat_memory_test_20260318.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

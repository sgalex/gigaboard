"""Fetch ContentNode via API and check lineage."""
import requests
import json

# Get auth token (replace with actual token from localStorage)
# For now, let's just try without auth
node_id = "3feea70a-aa30-454e-98b9-96fb9a0feaba"

try:
    response = requests.get(
        f"http://localhost:8000/api/v1/content-nodes/{node_id}",
        headers={"Authorization": "Bearer YOUR_TOKEN_HERE"}  # Replace with actual token
    )
    
    if response.status_code == 200:
        data = response.json()
        print("✅ ContentNode fetched successfully")
        print(f"\n📊 Lineage:")
        print(json.dumps(data.get("lineage", {}), indent=2))
        
        transform_history = data.get("lineage", {}).get("transformation_history", [])
        print(f"\n🔧 Transformation History ({len(transform_history)} items):")
        for idx, t in enumerate(transform_history):
            print(f"  {idx + 1}. {t.get('operation')} - {t.get('description')}")
            print(f"     code_snippet length: {len(t.get('code_snippet', ''))}")
    else:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"Error: {e}")

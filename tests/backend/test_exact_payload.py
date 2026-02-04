"""Test exact payload from frontend."""
from app.schemas import DataNodeCreate
from pydantic import ValidationError
import json

# Exact data from browser console
test_data = {
    "name": "тест",
    "data_source_type": "sql_query",
    "data_node_type": "text",
    "x": 100,
    "y": 100,
    "data": {"content": "test content", "needs_ai_processing": True},
    "text_content": "test content"
}

print("Testing with exact frontend data:")
print(json.dumps(test_data, indent=2, ensure_ascii=False))
print()

try:
    node = DataNodeCreate(**test_data)
    print("✅ SUCCESS! Schema validated")
    print(f"Schema dump: {node.model_dump()}")
except ValidationError as e:
    print("❌ VALIDATION ERROR:")
    print(e)
    print("\nDetailed errors:")
    for error in e.errors():
        print(f"  - Field: {error['loc']}")
        print(f"    Type: {error['type']}")
        print(f"    Message: {error['msg']}")
        print()

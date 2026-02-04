"""Test DataNodeCreate schema directly."""
from app.schemas import DataNodeCreate
from pydantic import ValidationError
import json

# Test data without board_id
test_data = {
    "name": "Test Node",
    "description": "Testing",
    "data_source_type": "sql_query",
    "data_node_type": "text",
    "text_content": "SELECT * FROM test",
    "query": "SELECT * FROM test",
    "data": {},
    "x": 50,
    "y": 50
}

print("Testing DataNodeCreate with data (NO board_id):")
print(json.dumps(test_data, indent=2))
print()

try:
    node = DataNodeCreate(**test_data)
    print("✅ SUCCESS! DataNodeCreate validated correctly")
    print(f"Created schema: {node.model_dump()}")
except ValidationError as e:
    print("❌ VALIDATION ERROR:")
    print(e.json(indent=2))

# Now test with board_id (should work but board_id will be ignored)
print("\n" + "="*60)
test_data_with_board_id = test_data.copy()
test_data_with_board_id["board_id"] = "56fa26c6-5c91-4d5d-a032-34cc534a94ec"

print("Testing DataNodeCreate with data (WITH board_id - should be ignored):")
print(json.dumps(test_data_with_board_id, indent=2))
print()

try:
    node = DataNodeCreate(**test_data_with_board_id)
    print("✅ Schema accepted board_id (will be ignored in service)")
    print(f"board_id in schema fields: {'board_id' in DataNodeCreate.model_fields}")
except ValidationError as e:
    print("❌ VALIDATION ERROR:")
    print(e.json(indent=2))

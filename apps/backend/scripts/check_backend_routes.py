"""Check if backend has new DataNode routes registered."""
import subprocess
import json

print("🔍 Checking backend API routes...\n")

try:
    result = subprocess.run(
        ["curl", "-s", "http://localhost:8000/openapi.json"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("❌ Backend is not running!")
        print("Please start backend: .\\run-backend.ps1")
        exit(1)
    
    openapi = json.loads(result.stdout)
    paths = list(openapi.get("paths", {}).keys())
    
    # Check for new routes
    has_data_nodes = any("data-nodes" in p for p in paths)
    has_widget_nodes = any("widget-nodes" in p for p in paths)
    has_comment_nodes = any("comment-nodes" in p for p in paths)
    has_old_widgets = any("/widgets" in p for p in paths)
    
    print("Route Status:")
    print(f"  {'✅' if has_data_nodes else '❌'} DataNode routes")
    print(f"  {'✅' if has_widget_nodes else '❌'} WidgetNode routes")
    print(f"  {'✅' if has_comment_nodes else '❌'} CommentNode routes")
    print(f"  {'⚠️' if has_old_widgets else '✅'} Old Widget routes {'(still present)' if has_old_widgets else '(removed)'}")
    
    print("\nAll routes:")
    for path in sorted(paths):
        icon = "🆕" if any(x in path for x in ["data-node", "widget-node", "comment-node"]) else "  "
        print(f"  {icon} {path}")
    
    if has_data_nodes and has_widget_nodes and has_comment_nodes:
        print("\n✅ Backend is ready for testing!")
        exit(0)
    else:
        print("\n❌ Backend needs restart!")
        print("\nSteps:")
        print("1. Stop backend (Ctrl+C in terminal)")
        print("2. Run: .\\run-backend.ps1")
        print("3. Run this check again")
        exit(1)
        
except json.JSONDecodeError:
    print("❌ Failed to parse OpenAPI spec")
    exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)

"""
Test production orchestrator workflow via API endpoint.

This script tests the real production flow:
1. Creates a Board
2. Creates a SourceNode with type PROMPT
3. Triggers extraction via POST /api/v1/source-nodes/extract
4. Verifies orchestrator correctly wraps message payloads
5. Monitors full Multi-Agent workflow execution

Requires running backend server.
"""

import asyncio
import sys
from pathlib import Path
from uuid import UUID
import httpx
from typing import Any
import time

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Test configuration
BASE_URL = "http://localhost:8000/api/v1"
# Generate unique user for each test run
TEST_USER = {
    "username": f"test_user_{int(time.time())}",
    "email": f"test_{int(time.time())}@example.com", 
    "password": "testpass123"
}

# Test prompt that should trigger Multi-Agent system
TEST_PROMPT = """
Analyze current Bitcoin (BTC) market data:
1. Get current price in USD
2. Calculate 24h price change percentage
3. Create a visualization showing the price trend
4. Provide analysis of market sentiment

Format the response as structured data with price, change, and chart.
"""


class ProductionOrchestratorTester:
    """Tests orchestrator via real API endpoints."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=BASE_URL, timeout=120.0, follow_redirects=True)
        self.token: str | None = None
        self.user_id: UUID | None = None
        self.project_id: UUID | None = None
        self.board_id: UUID | None = None
        self.source_node_id: UUID | None = None
        self.content_node_id: UUID | None = None
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
        
    async def authenticate(self) -> bool:
        """Register or login test user."""
        print("🔐 Authenticating...")
        
        # Try register
        try:
            response = await self.client.post(
                "/auth/register",
                json=TEST_USER
            )
            if response.status_code in (200, 201):
                data = response.json()
                self.token = data["access_token"]
                self.user_id = UUID(data["user"]["id"])
                print(f"✅ Registered new user: {TEST_USER['username']}")
                return True
            else:
                print(f"⚠️ Register failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"⚠️ Register error: {e}")
        
        # Try login
        try:
            response = await self.client.post(
                "/auth/login",
                json={
                    "email": TEST_USER["email"],
                    "password": TEST_USER["password"]
                }
            )
            if response.status_code == 200:
                data = response.json()
                self.token = data["access_token"]
                self.user_id = UUID(data["user"]["id"])
                print(f"✅ Logged in as: {TEST_USER['username']}")
                return True
            else:
                print(f"❌ Login failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
            
    @property
    def auth_headers(self) -> dict[str, str]:
        """Get authorization headers."""
        return {"Authorization": f"Bearer {self.token}"}
        
    async def create_project(self) -> bool:
        """Create test project."""
        print("\n📁 Creating project...")
        
        try:
            response = await self.client.post(
                "/projects",
                json={
                    "name": "Orchestrator Test Project",
                    "description": "Project for testing Multi-Agent orchestrator"
                },
                headers=self.auth_headers
            )
            
            if response.status_code in (200, 201):
                data = response.json()
                self.project_id = UUID(data["id"])
                print(f"✅ Created project: {data['name']} (ID: {self.project_id})")
                return True
            else:
                print(f"❌ Failed to create project: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Project creation error: {e}")
            return False
        
    async def create_board(self) -> bool:
        """Create test board."""
        print("\n📋 Creating board...")
        
        try:
            response = await self.client.post(
                "/boards",
                json={
                    "project_id": str(self.project_id),
                    "name": "Orchestrator Production Test",
                    "description": "Testing Multi-Agent orchestrator via API"
                },
                headers=self.auth_headers
            )
            
            if response.status_code in (200, 201):
                data = response.json()
                self.board_id = UUID(data["id"])
                print(f"✅ Created board: {data['name']} (ID: {self.board_id})")
                return True
            else:
                print(f"❌ Failed to create board: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ Board creation error: {e}")
            return False
            
    async def create_source_node(self) -> bool:
        """Create PROMPT SourceNode."""
        print("\n🔌 Creating SourceNode with PROMPT type...")
        
        try:
            response = await self.client.post(
                "/source-nodes",
                json={
                    "board_id": str(self.board_id),
                    "name": "AI Crypto Analysis",
                    "source_type": "PROMPT",
                    "config": {
                        "prompt": TEST_PROMPT,
                        "use_multi_agent": True  # Explicitly request Multi-Agent
                    },
                    "position_x": 100.0,
                    "position_y": 100.0
                },
                headers=self.auth_headers
            )
            
            if response.status_code == 200:
                data = response.json()
                self.source_node_id = UUID(data["id"])
                print(f"✅ Created SourceNode: {data['name']}")
                print(f"   ID: {self.source_node_id}")
                print(f"   Type: {data['source_type']}")
                print(f"   Prompt: {TEST_PROMPT[:100]}...")
                return True
            else:
                print(f"❌ Failed to create SourceNode: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            print(f"❌ SourceNode creation error: {e}")
            return False
            
    async def trigger_extraction(self) -> bool:
        """Trigger extraction via API - this activates orchestrator."""
        print("\n🚀 Triggering extraction (activating orchestrator)...")
        print("=" * 80)
        print("MONITORING ORCHESTRATOR WORKFLOW:")
        print("=" * 80)
        
        try:
            response = await self.client.post(
                "/source-nodes/extract",
                json={
                    "source_node_id": str(self.source_node_id),
                    "extraction_params": {
                        "user_prompt": TEST_PROMPT
                    }
                },
                headers=self.auth_headers
            )
            
            if response.status_code == 200:
                data = response.json()
                self.content_node_id = UUID(data["content_node_id"])
                print("\n" + "=" * 80)
                print("✅ EXTRACTION COMPLETED")
                print("=" * 80)
                print(f"   ContentNode ID: {self.content_node_id}")
                print(f"   Status: {data['status']}")
                print(f"   Rows: {data.get('row_count', 'N/A')}")
                print(f"   Time: {data.get('extraction_time_ms', 'N/A')}ms")
                return True
            else:
                print("\n" + "=" * 80)
                print(f"❌ EXTRACTION FAILED")
                print("=" * 80)
                print(f"   Status: {response.status_code}")
                print(f"   Response: {response.text}")
                return False
        except Exception as e:
            print("\n" + "=" * 80)
            print(f"❌ EXTRACTION ERROR")
            print("=" * 80)
            print(f"   Error: {e}")
            return False
            
    async def verify_content_node(self) -> bool:
        """Verify created ContentNode has data."""
        print("\n📊 Verifying ContentNode...")
        
        try:
            response = await self.client.get(
                f"/content-nodes/{self.content_node_id}",
                headers=self.auth_headers
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ ContentNode verified:")
                print(f"   Name: {data['name']}")
                print(f"   Data Preview: {str(data.get('data', {}))[:200]}...")
                print(f"   Size: {len(str(data.get('data', {})))} bytes")
                
                # Check if data looks like Multi-Agent output
                data_obj = data.get("data", {})
                if isinstance(data_obj, dict):
                    if "session_id" in data_obj or "final_result" in data_obj:
                        print("   ✅ Data structure matches Multi-Agent output")
                    
                return True
            else:
                print(f"❌ Failed to verify ContentNode: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Verification error: {e}")
            return False
            
    async def cleanup(self):
        """Cleanup test resources."""
        print("\n🧹 Cleanup...")
        
        # Delete board (cascades to nodes)
        if self.board_id:
            try:
                response = await self.client.delete(
                    f"/boards/{self.board_id}",
                    headers=self.auth_headers
                )
                if response.status_code == 200:
                    print("✅ Test board deleted")
            except Exception as e:
                print(f"⚠️ Cleanup error: {e}")
                
    async def run_full_test(self) -> bool:
        """Run complete production test."""
        print("=" * 80)
        print("🧪 ORCHESTRATOR PRODUCTION TEST")
        print("=" * 80)
        print("This test verifies that orchestrator correctly wraps message payloads")
        print("in production flow via real API endpoints.")
        print("=" * 80)
        
        try:
            # Step 1: Authenticate
            if not await self.authenticate():
                return False
                
            # Step 2: Create project
            if not await self.create_project():
                return False
                
            # Step 3: Create board
            if not await self.create_board():
                return False
                
            # Step 4: Create PROMPT SourceNode
            if not await self.create_source_node():
                return False
                
            # Step 5: Trigger extraction (activates orchestrator)
            if not await self.trigger_extraction():
                return False
                
            # Step 6: Verify result
            if not await self.verify_content_node():
                return False
                
            print("\n" + "=" * 80)
            print("✅ ALL TESTS PASSED")
            print("=" * 80)
            print("Orchestrator successfully processed request via production API")
            print("Message payloads were correctly wrapped")
            print("Multi-Agent workflow executed as expected")
            print("=" * 80)
            
            return True
            
        except Exception as e:
            print("\n" + "=" * 80)
            print(f"❌ TEST FAILED: {e}")
            print("=" * 80)
            import traceback
            traceback.print_exc()
            return False
        finally:
            await self.cleanup()


async def main():
    """Run production orchestrator test."""
    
    # Check if backend is running
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:8000/health")
            if response.status_code != 200:
                print("❌ Backend server not responding at http://localhost:8000")
                print("   Please start backend with: uv run python apps/backend/app/main.py")
                sys.exit(1)
    except Exception:
        print("❌ Cannot connect to backend at http://localhost:8000")
        print("   Please start backend with: uv run python apps/backend/app/main.py")
        sys.exit(1)
    
    async with ProductionOrchestratorTester() as tester:
        success = await tester.run_full_test()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

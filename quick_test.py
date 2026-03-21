#!/usr/bin/env python3
"""
Quick Fabric MCP Diagnostic Test
Run this on your VM to verify everything works.
"""

import asyncio
import aiohttp
import sys

# Configuration
FABRIC_URL = "https://fabric.perceptor.us"
AUTH_TOKEN = "dev-shared-secret"


async def test_health():
    """Test basic connectivity"""
    print("\n🩺 Testing Health Endpoint...")
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{FABRIC_URL}/health") as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"  ✅ Server up: {data.get('version', 'unknown')}")
                return True
            else:
                print(f"  ❌ Health check failed: {resp.status}")
                return False


async def test_auth():
    """Test authentication"""
    print("\n🔐 Testing Authentication...")
    async with aiohttp.ClientSession() as session:
        # Should fail without auth
        async with session.post(
            f"{FABRIC_URL}/mcp/call",
            json={"name": "fabric.health", "arguments": {}}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                if not data.get("ok") and "auth" in str(data.get("error", {}).get("code", "")).lower():
                    print("  ✅ Correctly rejects unauthenticated requests")
                else:
                    print("  ⚠️  Warning: Unauthenticated request succeeded")
            
        # Should succeed with auth
        async with session.post(
            f"{FABRIC_URL}/mcp/call",
            json={"name": "fabric.health", "arguments": {}},
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
        ) as resp:
            data = await resp.json()
            if data.get("ok"):
                print("  ✅ Authenticated requests work")
                return True
            else:
                print(f"  ❌ Auth failed: {data.get('error')}")
                return False


async def test_tools():
    """Test tool calls"""
    print("\n🛠️  Testing Tool Calls...")
    async with aiohttp.ClientSession() as session:
        # Test web search
        async with session.post(
            f"{FABRIC_URL}/mcp/call",
            json={
                "name": "fabric.tool.call",
                "arguments": {
                    "tool_id": "web.brave_search",
                    "capability": "search",
                    "parameters": {"query": "test", "max_results": 1}
                }
            },
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
        ) as resp:
            data = await resp.json()
            if data.get("ok"):
                results = len(data["result"].get("results", []))
                print(f"  ✅ Web search: {results} results")
            else:
                print(f"  ❌ Web search failed: {data.get('error')}")
                return False
        
        # Test math
        async with session.post(
            f"{FABRIC_URL}/mcp/call",
            json={
                "name": "fabric.tool.call",
                "arguments": {
                    "tool_id": "math.calculate",
                    "capability": "eval",
                    "parameters": {"expression": "2+2"}
                }
            },
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
        ) as resp:
            data = await resp.json()
            if data.get("ok") and data["result"].get("result") == 4:
                print("  ✅ Math: 2+2 = 4")
            else:
                print(f"  ❌ Math failed: {data.get('error')}")
                return False
        
        return True


async def test_a2a_messaging():
    """Test A2A messaging"""
    print("\n📨 Testing A2A Messaging...")
    async with aiohttp.ClientSession() as session:
        # Test send
        async with session.post(
            f"{FABRIC_URL}/mcp/call",
            json={
                "name": "fabric.message.send",
                "arguments": {
                    "to_agent": "test_agent",
                    "from_agent": "diagnostic",
                    "message_type": "test",
                    "payload": {"test": True}
                }
            },
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
        ) as resp:
            data = await resp.json()
            if data.get("ok"):
                print(f"  ✅ Message sent: {data['result'].get('message_id', 'N/A')[:20]}...")
            elif "A2A messaging not available" in str(data.get("error", {}).get("message", "")):
                print("  ⚠️  A2A messaging disabled (Redis not configured)")
                return None  # Not a failure, just not configured
            else:
                print(f"  ❌ Send failed: {data.get('error')}")
                return False
        
        # Test queue status
        async with session.post(
            f"{FABRIC_URL}/mcp/call",
            json={
                "name": "fabric.message.queue_status",
                "arguments": {"agent_id": "test_agent"}
            },
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
        ) as resp:
            data = await resp.json()
            if data.get("ok"):
                depth = data["result"].get("queue_depth", 0)
                print(f"  ✅ Queue status: {depth} messages pending")
            else:
                print(f"  ❌ Queue status failed: {data.get('error')}")
                return False
        
        # Test receive
        async with session.post(
            f"{FABRIC_URL}/mcp/call",
            json={
                "name": "fabric.message.receive",
                "arguments": {
                    "agent_id": "test_agent",
                    "count": 10,
                    "block_ms": 1000
                }
            },
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
        ) as resp:
            data = await resp.json()
            if data.get("ok"):
                count = len(data["result"].get("messages", []))
                print(f"  ✅ Received: {count} messages")
                
                # Acknowledge if we got messages
                if count > 0:
                    msg_ids = [m["_stream_id"] for m in data["result"]["messages"]]
                    async with session.post(
                        f"{FABRIC_URL}/mcp/call",
                        json={
                            "name": "fabric.message.acknowledge",
                            "arguments": {
                                "agent_id": "test_agent",
                                "message_ids": msg_ids
                            }
                        },
                        headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
                    ) as ack_resp:
                        ack_data = await ack_resp.json()
                        if ack_data.get("ok"):
                            print(f"  ✅ Acknowledged: {count} messages")
                        else:
                            print(f"  ⚠️  Ack failed: {ack_data.get('error')}")
            else:
                print(f"  ❌ Receive failed: {data.get('error')}")
                return False
        
        return True


async def main():
    print("=" * 60)
    print("🔬 Fabric MCP Quick Diagnostic")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Health", await test_health()))
    results.append(("Auth", await test_auth()))
    results.append(("Tools", await test_tools()))
    a2a_result = await test_a2a_messaging()
    results.append(("A2A Messaging", a2a_result))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)
    
    passed = 0
    failed = 0
    skipped = 0
    
    for name, result in results:
        if result is True:
            print(f"  ✅ {name}: PASS")
            passed += 1
        elif result is False:
            print(f"  ❌ {name}: FAIL")
            failed += 1
        else:
            print(f"  ⚠️  {name}: SKIPPED (not configured)")
            skipped += 1
    
    print("=" * 60)
    print(f"Total: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed > 0:
        print("\n❌ Some tests failed. Check the output above.")
        sys.exit(1)
    elif passed == len(results):
        print("\n🎉 All tests passed! Fabric is ready for Aether integration.")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests skipped. Core functionality works.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())

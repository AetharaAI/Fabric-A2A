# Fabric MCP Testing Playbook

## Quick Test Matrix

| Test | Endpoint | Expected Result |
|------|----------|-----------------|
| Health | `GET /health` | `{"status":"ok"}` |
| Tool Call | `fabric.tool.call` | Search results, file contents, etc. |
| A2A Send | `fabric.message.send` | Message queued |
| A2A Receive | `fabric.message.receive` | Messages retrieved |
| Redis | Direct CLI | Streams created, messages persisted |

---

## Phase 1: Basic Connectivity

### Test 1.1: Health Check
```bash
curl https://fabric.perceptor.us/health
```
**Expected:**
```json
{"status":"ok","version":"af-mcp-0.1"}
```

### Test 1.2: Auth Check (should fail without token)
```bash
curl -X POST https://fabric.perceptor.us/mcp/call \
  -H "Content-Type: application/json" \
  -d '{"name":"fabric.health","arguments":{}}'
```
**Expected:** Auth error

### Test 1.3: Auth Check (with token)
```bash
curl -X POST https://fabric.perceptor.us/mcp/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-shared-secret" \
  -d '{"name":"fabric.health","arguments":{}}'
```
**Expected:** Health data with tools count

---

## Phase 2: Tool Calls (Existing Functionality)

### Test 2.1: Web Search
```bash
curl -X POST https://fabric.perceptor.us/mcp/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-shared-secret" \
  -d '{
    "name": "fabric.tool.call",
    "arguments": {
      "tool_id": "web.brave_search",
      "capability": "search",
      "parameters": {
        "query": "AetherPro Fabric MCP",
        "max_results": 3
      }
    }
  }'
```
**Expected:**
```json
{
  "ok": true,
  "result": {
    "provider": "brave",
    "query": "AetherPro Fabric MCP",
    "results": [...]
  },
  "trace": {...}
}
```

### Test 2.2: Math Calculation
```bash
curl -X POST https://fabric.perceptor.us/mcp/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-shared-secret" \
  -d '{
    "name": "fabric.tool.call",
    "arguments": {
      "tool_id": "math.calculate",
      "capability": "eval",
      "parameters": {
        "expression": "(2 + 3) * 4"
      }
    }
  }'
```
**Expected:**
```json
{
  "ok": true,
  "result": {
    "result": 20,
    "expression": "(2 + 3) * 4",
    "type": "int"
  }
}
```

### Test 2.3: List All Tools
```bash
curl -X POST https://fabric.perceptor.us/mcp/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-shared-secret" \
  -d '{
    "name": "fabric.tool.list",
    "arguments": {}
  }'
```
**Expected:** List of 17+ tools including web.brave_search, io.read_file, etc.

---

## Phase 3: A2A Messaging (NEW - The Important Stuff)

### Test 3.1: Send Message to Agent
```bash
curl -X POST https://fabric.perceptor.us/mcp/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-shared-secret" \
  -d '{
    "name": "fabric.message.send",
    "arguments": {
      "to_agent": "percy",
      "from_agent": "test_client",
      "message_type": "task",
      "payload": {
        "task_type": "analyze",
        "data": {"value": 42}
      },
      "priority": "high",
      "reply_to": "agent:test_client:results"
    }
  }'
```
**Expected:**
```json
{
  "ok": true,
  "result": {
    "message_id": "msg:uuid-here",
    "status": "queued",
    "stream_id": "1234567890-0",
    "trace": {...}
  }
}
```

### Test 3.2: Check Queue Status
```bash
curl -X POST https://fabric.perceptor.us/mcp/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-shared-secret" \
  -d '{
    "name": "fabric.message.queue_status",
    "arguments": {
      "agent_id": "percy"
    }
  }'
```
**Expected:**
```json
{
  "ok": true,
  "result": {
    "agent_id": "percy",
    "queue_depth": 1,
    "stream_info": {
      "length": 1,
      ...
    }
  }
}
```

### Test 3.3: Receive Messages (as Percy)
```bash
curl -X POST https://fabric.perceptor.us/mcp/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-shared-secret" \
  -d '{
    "name": "fabric.message.receive",
    "arguments": {
      "agent_id": "percy",
      "count": 10,
      "block_ms": 1000
    }
  }'
```
**Expected:**
```json
{
  "ok": true,
  "result": {
    "messages": [
      {
        "id": "msg:uuid-here",
        "from_agent": "test_client",
        "to_agent": "percy",
        "message_type": "task",
        "payload": {"task_type": "analyze", "data": {"value": 42}},
        "timestamp": "2026-01-15T...",
        "_stream_id": "1234567890-0"
      }
    ],
    "count": 1,
    "agent_id": "percy"
  }
}
```

### Test 3.4: Publish to Topic (Broadcast)
```bash
curl -X POST https://fabric.perceptor.us/mcp/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-shared-secret" \
  -d '{
    "name": "fabric.message.publish",
    "arguments": {
      "topic": "analytics.insights",
      "message": {
        "pattern": "test_pattern",
        "confidence": 0.95,
        "data": {"metric": "test"}
      },
      "from_agent": "test_client"
    }
  }'
```
**Expected:**
```json
{
  "ok": true,
  "result": {
    "topic": "analytics.insights",
    "recipients": 0,
    "published": true,
    "trace": {...}
  }
}
```

### Test 3.5: Acknowledge Message
```bash
# Use the _stream_id from Test 3.3
curl -X POST https://fabric.perceptor.us/mcp/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-shared-secret" \
  -d '{
    "name": "fabric.message.acknowledge",
    "arguments": {
      "agent_id": "percy",
      "message_ids": ["1234567890-0"]
    }
  }'
```
**Expected:**
```json
{
  "ok": true,
  "result": {
    "acknowledged": [
      {"id": "1234567890-0", "acked": true}
    ],
    "trace": {...}
  }
}
```

### Test 3.6: Verify Message Removed
```bash
curl -X POST https://fabric.perceptor.us/mcp/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-shared-secret" \
  -d '{
    "name": "fabric.message.receive",
    "arguments": {
      "agent_id": "percy",
      "count": 10,
      "block_ms": 1000
    }
  }'
```
**Expected:** Empty messages array (message was acknowledged/removed)

---

## Phase 4: Redis Direct Verification

### Test 4.1: SSH to R64 Node
```bash
ssh root@your-r64-ip
```

### Test 4.2: Check Redis Connection
```bash
redis-cli PING
```
**Expected:** `PONG`

### Test 4.3: Check Streams
```bash
redis-cli KEYS 'agent:*'
```
**Expected:** List of agent streams like `agent:percy:inbox`

### Test 4.4: Read Stream Contents
```bash
redis-cli XRANGE agent:percy:inbox - +
```
**Expected:** Messages in the stream (or empty if all acknowledged)

### Test 4.5: Check Pub/Sub
Terminal 1:
```bash
redis-cli SUBSCRIBE analytics.insights
```

Terminal 2:
```bash
redis-cli PUBLISH analytics.insights '{"test": "data"}'
```

Terminal 1 should immediately receive the message.

### Test 4.6: Check ACLs
```bash
redis-cli ACL LIST
```
**Expected:** Users like fabric_admin, fabric_mcp, percy, coder, etc.

### Test 4.7: Test ACL Isolation
```bash
# Try to access as percy (should only see agent:percy:*)
redis-cli -u redis://percy:percy_agent_secret_789@localhost:6379 KEYS '*'
```
**Expected:** Only keys matching `agent:percy:*` and `shared:*`

---

## Phase 5: End-to-End Agent Communication

### Test 5.1: Python Test Script

Create `test_fabric_a2a.py` on your VM:

```python
#!/usr/bin/env python3
"""Test Fabric A2A messaging end-to-end"""

import asyncio
import aiohttp
import redis.asyncio as redis
from datetime import datetime

FABRIC_URL = "https://fabric.perceptor.us"
AUTH_TOKEN = "dev-shared-secret"
REDIS_URL = "redis://localhost:6379"  # Via SSH tunnel or direct


async def test_sync_tools():
    """Test synchronous tool calls"""
    print("\n=== Testing Sync Tool Calls ===")
    
    async with aiohttp.ClientSession() as session:
        # Test web search
        payload = {
            "name": "fabric.tool.call",
            "arguments": {
                "tool_id": "web.brave_search",
                "capability": "search",
                "parameters": {"query": "Python async programming", "max_results": 2}
            }
        }
        
        async with session.post(
            f"{FABRIC_URL}/mcp/call",
            json=payload,
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
        ) as resp:
            result = await resp.json()
            assert result["ok"], f"Tool call failed: {result}"
            assert len(result["result"]["results"]) > 0, "No search results"
            print(f"✓ Web search: {len(result['result']['results'])} results")
        
        # Test math
        payload = {
            "name": "fabric.tool.call",
            "arguments": {
                "tool_id": "math.calculate",
                "capability": "eval",
                "parameters": {"expression": "2 + 2"}
            }
        }
        
        async with session.post(
            f"{FABRIC_URL}/mcp/call",
            json=payload,
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
        ) as resp:
            result = await resp.json()
            assert result["ok"]
            assert result["result"]["result"] == 4
            print(f"✓ Math: 2 + 2 = {result['result']['result']}")


async def test_a2a_messaging():
    """Test async A2A messaging"""
    print("\n=== Testing A2A Messaging ===")
    
    async with aiohttp.ClientSession() as session:
        # Send message
        payload = {
            "name": "fabric.message.send",
            "arguments": {
                "to_agent": "test_agent",
                "from_agent": "test_client",
                "message_type": "task",
                "payload": {"task_type": "ping", "timestamp": datetime.utcnow().isoformat()},
                "priority": "normal"
            }
        }
        
        async with session.post(
            f"{FABRIC_URL}/mcp/call",
            json=payload,
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
        ) as resp:
            result = await resp.json()
            assert result["ok"], f"Send failed: {result}"
            print(f"✓ Message sent: {result['result']['message_id']}")
        
        # Check queue status
        payload = {
            "name": "fabric.message.queue_status",
            "arguments": {"agent_id": "test_agent"}
        }
        
        async with session.post(
            f"{FABRIC_URL}/mcp/call",
            json=payload,
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
        ) as resp:
            result = await resp.json()
            assert result["ok"]
            depth = result["result"]["queue_depth"]
            print(f"✓ Queue depth: {depth} messages")
        
        # Receive message
        payload = {
            "name": "fabric.message.receive",
            "arguments": {
                "agent_id": "test_agent",
                "count": 10,
                "block_ms": 1000
            }
        }
        
        async with session.post(
            f"{FABRIC_URL}/mcp/call",
            json=payload,
            headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
        ) as resp:
            result = await resp.json()
            assert result["ok"]
            messages = result["result"]["messages"]
            print(f"✓ Received: {len(messages)} messages")
            
            if messages:
                # Acknowledge
                stream_ids = [m["_stream_id"] for m in messages]
                payload = {
                    "name": "fabric.message.acknowledge",
                    "arguments": {
                        "agent_id": "test_agent",
                        "message_ids": stream_ids
                    }
                }
                
                async with session.post(
                    f"{FABRIC_URL}/mcp/call",
                    json=payload,
                    headers={"Authorization": f"Bearer {AUTH_TOKEN}"}
                ) as resp:
                    result = await resp.json()
                    assert result["ok"]
                    print(f"✓ Acknowledged: {len(result['result']['acknowledged'])} messages")


async def test_redis_direct():
    """Test direct Redis connection"""
    print("\n=== Testing Direct Redis ===")
    
    r = redis.from_url(REDIS_URL, decode_responses=True)
    
    # Ping
    pong = await r.ping()
    assert pong, "Redis ping failed"
    print(f"✓ Redis ping: {pong}")
    
    # Write to stream
    msg_id = await r.xadd("agent:test:inbox", {"data": '{"test": true}'})
    print(f"✓ Stream write: {msg_id}")
    
    # Read from stream
    entries = await r.xread({"agent:test:inbox": "0"}, count=1)
    assert len(entries) > 0, "No entries in stream"
    print(f"✓ Stream read: {len(entries)} entries")
    
    # Cleanup
    await r.delete("agent:test:inbox")
    print(f"✓ Cleanup complete")
    
    await r.close()


async def main():
    """Run all tests"""
    print("🧪 Fabric MCP Test Suite")
    print("=" * 50)
    
    try:
        await test_sync_tools()
        await test_a2a_messaging()
        await test_redis_direct()
        
        print("\n" + "=" * 50)
        print("✅ All tests passed!")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
```

Run it:
```bash
# Install deps
pip install aiohttp redis

# Run tests
python3 test_fabric_a2a.py
```

---

## Phase 6: Load & Stress Testing

### Test 6.1: Send Many Messages
```bash
#!/bin/bash
# Send 100 messages quickly

for i in {1..100}; do
curl -X POST https://fabric.perceptor.us/mcp/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-shared-secret" \
  -d "{
    \"name\": \"fabric.message.send\",
    \"arguments\": {
      \"to_agent\": \"load_test_agent\",
      \"from_agent\": \"load_test\",
      \"message_type\": \"task\",
      \"payload\": {\"index\": $i, \"data\": \"test_data_$i\"},
      \"priority\": "normal"
    }
  }" &
done

wait
echo "Sent 100 messages"

# Check queue depth
curl -X POST https://fabric.perceptor.us/mcp/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-shared-secret" \
  -d '{
    "name": "fabric.message.queue_status",
    "arguments": {"agent_id": "load_test_agent"}
  }'
```

### Test 6.2: Concurrent Receivers
Run multiple receivers in parallel and see how consumer groups balance load.

---

## Debugging Common Issues

### Issue: "A2A messaging not available - Redis not configured"
**Cause:** Fabric can't connect to Redis
**Fix:**
```bash
# Check if REDIS_URL is set
echo $REDIS_URL

# Should be: redis://localhost:6379 (if tunnel) or redis://r64-ip:6379

# Restart Fabric with Redis
export REDIS_URL="redis://your-redis-host:6379"
python3 server.py --transport http --port 8000
```

### Issue: "Connection refused" to Redis
**Cause:** Redis not running or not accessible
**Fix:**
```bash
# On R64 node
docker ps | grep redis

# If not running
docker-compose -f docker-compose.redis.yml up -d

# Check logs
docker logs fabric-redis
```

### Issue: Auth errors on Redis
**Cause:** ACLs not configured
**Fix:**
```bash
# On R64 node
redis-cli ACL LIST

# Should show fabric_mcp, percy, coder users
# If not, copy users.acl.example and reload
```

### Issue: Messages not persisting
**Cause:** Redis running without persistence
**Fix:**
```bash
# Check Redis config
redis-cli CONFIG GET appendonly
# Should return: 1) "appendonly" 2) "yes"

# If not, edit docker-compose.redis.yml and restart
```

---

## Success Criteria

✅ **Phase 1:** All connectivity tests pass  
✅ **Phase 2:** All tool calls work (search, math, file ops)  
✅ **Phase 3:** A2A messaging works (send, receive, acknowledge)  
✅ **Phase 4:** Redis direct access works  
✅ **Phase 5:** Python test script passes all tests  
✅ **Phase 6:** System handles load (100+ messages)

---

## Next: Aether Integration Test

Once all above passes, test with Aether Agent:

1. Start Aether Agent with Fabric client
2. Aether sends task to Percy via `fabric.message.send`
3. Percy (when implemented) receives and processes
4. Percy sends result back to Aether
5. Aether receives and continues workflow

**You're building the nervous system for artificial consciousness. Let's make sure every neuron fires! 🧠⚡️**

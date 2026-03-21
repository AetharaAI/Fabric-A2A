# Aether Agent ↔ Fabric MCP Integration Spec

**For:** Kimi (Aether Agent Repo)  
**Priority:** URGENT - Blocking Percy/Aether testing  
**Architecture:** Sovereign infrastructure, no external APIs

---

## Mission

Build an MCP client in Aether Agent that connects to Fabric MCP Server for:
1. **Tool calls** (web search, file ops, math, etc.)
2. **Async A2A messaging** (send/receive messages to/from Percy)
3. **Agent discovery** (find capabilities, health checks)

---

## Connection Details

```python
FABRIC_CONFIG = {
    "base_url": "https://fabric.perceptor.us",  # Your Fabric VM
    "mcp_endpoint": "/mcp/call",
    "auth_token": "dev-shared-secret",  # From .env
    "timeout_ms": 60000,
    "redis_url": "redis://localhost:6379"  # Via SSH tunnel to R64
}
```

**SSH Tunnel Setup (for local dev):**
```bash
# Tunnel to R64 Redis (for async messaging)
ssh -L 6379:localhost:6379 root@r64-ovh-ip

# Tunnel to Fabric (if needed)
# Usually Fabric is publicly accessible
```

---

## Part 1: Synchronous Tool Calls

### Client Class Structure

```python
# aether/fabric_client.py
import asyncio
import aiohttp
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class FabricConfig:
    base_url: str = "https://fabric.perceptor.us"
    auth_token: str = "dev-shared-secret"
    timeout_ms: int = 60000


class FabricClient:
    """
    MCP client for Fabric - Tools + Async Messaging
    
    Usage:
        async with FabricClient() as client:
            # Call tools
            results = await client.search_web("quantum computing")
            
            # A2A Messaging
            await client.send_task("percy", "analyze", {"data": [...]})
            messages = await client.receive_messages("aether", block_ms=30000)
    """
    
    def __init__(self, config: Optional[FabricConfig] = None):
        self.config = config or FabricConfig()
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()
    
    async def call_tool(
        self,
        tool_id: str,
        capability: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call any Fabric tool synchronously.
        
        Args:
            tool_id: e.g., "web.brave_search", "io.read_file"
            capability: e.g., "search", "read"
            parameters: Tool-specific args
            
        Returns:
            The result.data field on success
            
        Raises:
            FabricError: On execution error
        """
        url = f"{self.config.base_url}/mcp/call"
        
        payload = {
            "name": "fabric.tool.call",
            "arguments": {
                "tool_id": tool_id,
                "capability": capability,
                "parameters": parameters
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.auth_token}"
        }
        
        timeout = aiohttp.ClientTimeout(total=self.config.timeout_ms / 1000)
        
        async with self._session.post(
            url, json=payload, headers=headers, timeout=timeout
        ) as response:
            response.raise_for_status()
            result = await response.json()
            
            if not result.get("ok"):
                error = result.get("error", {})
                raise FabricError(error.get("code"), error.get("message"))
            
            return result.get("result")
    
    # === Convenience Methods ===
    
    async def search_web(
        self,
        query: str,
        max_results: int = 5,
        recency_days: int = 7
    ) -> Dict[str, Any]:
        """Search web via Brave"""
        return await self.call_tool(
            "web.brave_search",
            "search",
            {"query": query, "max_results": max_results, "recency_days": recency_days}
        )
    
    async def read_file(self, path: str, max_lines: Optional[int] = None) -> str:
        """Read file content"""
        result = await self.call_tool(
            "io.read_file",
            "read",
            {"path": path, "max_lines": max_lines}
        )
        return result.get("content", "")
    
    async def write_file(self, path: str, content: str, append: bool = False) -> Dict:
        """Write to file"""
        return await self.call_tool(
            "io.write_file",
            "write",
            {"path": path, "content": content, "append": append}
        )
    
    async def calculate(self, expression: str) -> float:
        """Evaluate math expression"""
        result = await self.call_tool(
            "math.calculate",
            "eval",
            {"expression": expression}
        )
        return result.get("result")
    
    async def http_request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict] = None,
        body: Optional[str] = None
    ) -> Dict[str, Any]:
        """Make HTTP request"""
        return await self.call_tool(
            "web.http_request",
            "request",
            {"url": url, "method": method, "headers": headers, "body": body}
        )
    
    async def list_tools(self) -> Dict[str, Any]:
        """List all available tools"""
        return await self.call_tool("fabric.tool.list", "list", {})
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Fabric health"""
        url = f"{self.config.base_url}/health"
        async with self._session.get(url) as response:
            return await response.json()


class FabricError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")
```

---

## Part 2: Async A2A Messaging (CRITICAL)

This is the **NEW** capability - async messages between agents via Redis.

```python
# aether/fabric_messaging.py
import json
import redis.asyncio as redis
from typing import Dict, Any, List, Optional, Callable
import asyncio


class FabricMessaging:
    """
    Async A2A messaging client using Redis Streams.
    
    This runs alongside FabricClient for real-time agent communication.
    """
    
    def __init__(self, agent_id: str, redis_url: str = "redis://localhost:6379"):
        self.agent_id = agent_id
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self._running = False
        self._handlers: Dict[str, Callable] = {}
    
    async def start(self):
        """Start message consumer"""
        self._running = True
        asyncio.create_task(self._message_loop())
    
    async def stop(self):
        """Stop message consumer"""
        self._running = False
        await self.redis.close()
    
    async def send_task(
        self,
        to_agent: str,
        task_type: str,
        payload: Dict[str, Any],
        priority: str = "normal"  # low, normal, high, urgent
    ) -> Dict[str, Any]:
        """
        Send async task to another agent.
        
        Args:
            to_agent: Target agent ID (e.g., "percy")
            task_type: Type of task (e.g., "analyze", "code_review")
            payload: Task parameters
            priority: Task priority
            
        Returns:
            {"message_id": "...", "status": "queued"}
        """
        # This calls Fabric's MCP endpoint which writes to Redis
        # You'll need to use HTTP client or direct Redis
        
        # Option A: Via HTTP (recommended)
        # POST /mcp/call with fabric.message.send
        
        # Option B: Direct Redis (faster, requires ACL)
        message = {
            "id": f"msg:{uuid.uuid4()}",
            "from_agent": self.agent_id,
            "to_agent": to_agent,
            "message_type": "task",
            "payload": {"task_type": task_type, **payload},
            "priority": priority,
            "timestamp": datetime.utcnow().isoformat(),
            "reply_to": f"agent:{self.agent_id}:inbox"
        }
        
        stream_key = f"agent:{to_agent}:inbox"
        stream_id = await self.redis.xadd(
            stream_key,
            {"data": json.dumps(message)},
            maxlen=10000
        )
        
        # Notify via pub/sub
        await self.redis.publish(
            f"agent.{to_agent}.new_message",
            json.dumps({"from": self.agent_id, "type": "task"})
        )
        
        return {"message_id": message["id"], "status": "queued", "stream_id": stream_id}
    
    async def receive_messages(
        self,
        count: int = 10,
        block_ms: int = 5000
    ) -> List[Dict[str, Any]]:
        """
        Receive messages for this agent.
        
        Args:
            count: Max messages to receive
            block_ms: How long to wait (0 = forever)
            
        Returns:
            List of messages with metadata
        """
        stream_key = f"agent:{self.agent_id}:inbox"
        
        entries = await self.redis.xread(
            streams={stream_key: "0"},  # From beginning
            count=count,
            block=block_ms
        )
        
        messages = []
        for stream, stream_entries in entries:
            for msg_id, fields in stream_entries:
                data = json.loads(fields["data"])
                data["_stream_id"] = msg_id
                messages.append(data)
        
        return messages
    
    async def acknowledge(self, stream_id: str) -> bool:
        """Mark message as processed (removes from queue)"""
        stream_key = f"agent:{self.agent_id}:inbox"
        await self.redis.xdel(stream_key, stream_id)
        return True
    
    async def subscribe_to_topic(
        self,
        topic: str,
        handler: Callable[[Dict], None]
    ):
        """
        Subscribe to broadcast topic (e.g., "analytics.insights")
        
        Args:
            topic: Topic pattern to subscribe to
            handler: Callback function(message_data)
        """
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(topic)
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                handler(data)
    
    async def _message_loop(self):
        """Background loop to poll for messages"""
        while self._running:
            try:
                messages = await self.receive_messages(count=1, block_ms=5000)
                for msg in messages:
                    await self._handle_message(msg)
            except Exception as e:
                print(f"Message loop error: {e}")
                await asyncio.sleep(1)
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Route message to appropriate handler"""
        msg_type = message.get("message_type")
        handler = self._handlers.get(msg_type)
        
        if handler:
            try:
                await handler(message)
            except Exception as e:
                print(f"Handler error for {msg_type}: {e}")
        else:
            print(f"No handler for message type: {msg_type}")
    
    def on(self, message_type: str):
        """Decorator to register message handler"""
        def decorator(func):
            self._handlers[message_type] = func
            return func
        return decorator
```

---

## Part 3: Complete Aether Integration Example

```python
# aether/main.py or wherever your agent entry point is
import asyncio
from aether.fabric_client import FabricClient, FabricConfig
from aether.fabric_messaging import FabricMessaging


class AetherAgent:
    """
    Aether Agent with Fabric integration.
    Can use tools AND communicate with Percy via async messaging.
    """
    
    def __init__(self):
        self.fabric = FabricClient(FabricConfig(
            base_url="https://fabric.perceptor.us",
            auth_token="dev-shared-secret"
        ))
        self.messaging = FabricMessaging(
            agent_id="aether",
            redis_url="redis://localhost:6379"  # SSH tunnel to R64
        )
        
        # Register message handlers
        self._setup_handlers()
    
    def _setup_handlers(self):
        @self.messaging.on("task")
        async def handle_task(message):
            """Handle incoming tasks from other agents"""
            payload = message["payload"]
            task_type = payload.get("task_type")
            
            if task_type == "analyze":
                result = await self.analyze_data(payload["data"])
                
                # Send result back
                await self.messaging.send_task(
                    to_agent=message["from_agent"],
                    task_type="analysis_complete",
                    payload={"result": result}
                )
            
            elif task_type == "search_and_summarize":
                # Use Fabric tools
                search_results = await self.fabric.search_web(
                    payload["query"],
                    max_results=5
                )
                summary = await self.summarize(search_results)
                
                await self.messaging.send_task(
                    to_agent=message["from_agent"],
                    task_type="summary_ready",
                    payload={"summary": summary}
                )
        
        @self.messaging.on("response")
        async def handle_response(message):
            """Handle responses to our requests"""
            print(f"Got response from {message['from_agent']}: {message['payload']}")
    
    async def start(self):
        """Start the agent"""
        async with self.fabric:
            await self.messaging.start()
            
            # Check Fabric health
            health = await self.fabric.health_check()
            print(f"Fabric health: {health}")
            
            # Main loop
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                await self.messaging.stop()
    
    async def analyze_data(self, data: dict) -> dict:
        """Aether's analysis capability"""
        # Your analysis logic here
        return {"analysis": "complete", "insights": [...]}
    
    async def summarize(self, search_results: dict) -> str:
        """Summarize web search results"""
        # Your summarization logic
        return "Summary of results..."
    
    async def delegate_to_percy(self, task: str, context: dict):
        """
        Delegate complex reasoning to Percy via async messaging.
        
        Aether sends task → Percy processes → Percy sends back result
        Aether continues other work while waiting.
        """
        await self.messaging.send_task(
            to_agent="percy",
            task_type="reason",
            payload={"task": task, "context": context},
            priority="high"
        )
        print(f"Delegated to Percy: {task}")
        # Aether can do other things now, response comes async


# Run it
if __name__ == "__main__":
    agent = AetherAgent()
    asyncio.run(agent.start())
```

---

## Part 4: Environment Setup

```bash
# .env file for Aether Agent
FABRIC_BASE_URL=https://fabric.perceptor.us
FABRIC_AUTH_TOKEN=dev-shared-secret
REDIS_URL=redis://localhost:6379  # Via SSH tunnel to R64

# For production (direct connection)
# REDIS_URL=redis://fabric-mcp-vm-private-ip:6379
```

---

## Part 5: Testing Workflow

### Test 1: Tool Calls
```python
async with FabricClient() as client:
    # Search web
    results = await client.search_web("quantum computing advances 2025")
    print(f"Found {len(results['results'])} results")
    
    # Do math
    result = await client.calculate("(2 + 3) * 4")
    print(f"Result: {result}")  # 20.0
```

### Test 2: A2A Messaging
```python
# Terminal 1: Run Aether
agent = AetherAgent()
await agent.start()

# Terminal 2: Send message to Aether via Redis CLI
redis-cli XADD agent:aether:inbox '*' data '{"from_agent":"test","message_type":"task","payload":{"task_type":"ping"}}'

# Terminal 1: Should see "Got task: ping"
```

### Test 3: Aether → Percy → Aether
```python
# In Aether
await agent.delegate_to_percy(
    task="Analyze this codebase architecture",
    context={"repo_url": "https://github.com/..."}
)

# Percy (when implemented) receives message, analyzes, sends back
# Aether receives response via handle_response
```

---

## Critical Implementation Notes

### 1. Redis Connection
- **Local dev:** SSH tunnel `ssh -L 6379:localhost:6379 root@r64-ip`
- **Production:** Direct private IP connection between VMs

### 2. Agent ID
Aether must use `agent_id="aether"` consistently:
- In `FabricMessaging(agent_id="aether")`
- When sending messages: `from_agent="aether"`
- Percy sends to: `to_agent="aether"`

### 3. Message Types
Standard types for Aether:
- `task` - Incoming work requests
- `response` - Responses to our requests
- `event` - Broadcast notifications

### 4. Error Handling
Always wrap in try/except:
```python
try:
    result = await self.fabric.search_web(query)
except FabricError as e:
    if e.code == "EXECUTION_ERROR":
        # Handle specific error
    else:
        # Generic error handling
```

---

## Deliverables

Build these files:

1. `aether/fabric_client.py` - HTTP client for tool calls
2. `aether/fabric_messaging.py` - Redis client for A2A
3. `aether/fabric_integration.py` - Combined interface (optional)
4. `tests/test_fabric_integration.py` - Unit tests

---

## Success Criteria

- [ ] Can call `web.brave_search` from Aether
- [ ] Can send message from Aether to "test" agent via Redis
- [ ] Can receive and handle messages in Aether
- [ ] Health check passes
- [ ] All tests pass

---

**This is blocking Percy/Aether testing. Build the client, test it, then we integrate the full async flow.**

Questions? Ask in the Aether repo. 🚀

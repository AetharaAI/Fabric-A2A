# Fabric MCP Integration Guide for Mastro Agent

**For:** Mastro Agent Integration  
**Purpose:** Complete guide to integrate with Fabric MCP Server  
**Authentication:** PSK or Passport (Keycloak OAuth)

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Authentication](#authentication)
4. [MCP Endpoints](#mcp-endpoints)
5. [Tool Calls](#tool-calls)
6. [Agent Communication](#agent-communication)
7. [Async Messaging](#async-messaging)
8. [Python Client Implementation](#python-client-implementation)
9. [Agent Registration](#agent-registration)
10. [ACL Security](#acl-security)
11. [Environment Setup](#environment-setup)

---

## Overview

Fabric MCP Server is a **model-agnostic, agent-agnostic message passing system** that provides:

- **Built-in Tools**: 20+ tools for file I/O, HTTP, math, text processing, etc.
- **Agent-to-Agent Communication**: Route calls between agents via MCP
- **Async Messaging**: Redis Streams for persistent task queues
- **Real-time Events**: Pub/Sub for broadcasts and notifications
- **Agent Registry**: PostgreSQL-backed discovery service

Your agent (Mastro) can:
1. **Call Fabric's built-in tools** directly
2. **Register itself** so other agents can discover and call it
3. **Send async messages** to other agents via Redis

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Your Agent (Mastro)                       │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          │ HTTP/HTTPS
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Fabric MCP Gateway                          │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐     │
│  │   MCP Server   │  │ Message Bus    │  │   Registry     │     │
│  │  HTTP/WS API   │  │ (Redis)        │  │ (PostgreSQL)   │     │
│  └────────────────┘  └────────────────┘  └────────────────┘     │
└─────────────────────────┬───────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Built-in     │  │ Other        │  │ Your Agent   │
│ Tools        │  │ Agents        │  │ (Registered) │
└──────────────┘  └──────────────┘  └──────────────┘
```

---

## Authentication

### Option 1: Pre-Shared Key (PSK)

Simple token-based auth for development:

```bash
# Start Fabric with PSK
python server.py --psk your-secret-key --transport http
```

**Usage:**
```bash
curl -H "Authorization: Bearer your-secret-key" \
  -X POST https://fabric.perceptor.us/mcp/call \
  -d '{"name": "fabric.tool.list", "arguments": {}}'
```

### Option 2: Passport (Keycloak OAuth)

For production with SSO and cryptographic verification:

```bash
# Configure Passport in fabric_config.yaml
fabric:
  auth:
    mode: passport
    passport_url: "https://passport.aetherpro.us"
    client_id: "fabric-mcp"
    client_secret: "your-client-secret"
    realm: "fabric"
```

**Token Request:**
```bash
# Get token from Passport
curl -X POST https://passport.aetherpro.us/realms/fabric/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=fabric-mcp" \
  -d "client_secret=your-client-secret"
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

**Usage with Passport Token:**
```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  -X POST https://fabric.perceptor.us/mcp/call \
  -d '{"name": "fabric.tool.list", "arguments": {}}'
```

**Passport Token Format:**
```json
{
  "passport": {
    "principal_id": "user:admin",
    "agent_passport_id": "agent:mastro#cert-001",
    "delegation": ["capability:reason", "capability:plan"],
    "expires_at": "2026-02-14T00:00:00Z",
    "signature": "base64-encoded-ed25519-signature",
    "key_id": "kid:xyz"
  }
}
```

---

## MCP Endpoints

### POST /mcp/call

Main endpoint for all MCP operations.

**Request:**
```json
POST /mcp/call
Authorization: Bearer <psk-or-token>
Content-Type: application/json

{
  "name": "fabric.tool.list",
  "arguments": {}
}
```

### POST /mcp/register_agent

Register your agent in the Fabric registry.

**Request:**
```json
POST /mcp/register_agent
Authorization: Bearer <master-secret>
Content-Type: application/json

{
  "agent_id": "mastro",
  "display_name": "Mastro Agent",
  "version": "1.0.0",
  "description": "Specialized reasoning and planning agent",
  "capabilities": [
    {
      "name": "reason",
      "description": "Complex reasoning and analysis",
      "streaming": true,
      "modalities": ["text"],
      "input_schema": {
        "type": "object",
        "properties": {
          "task": {"type": "string"},
          "context": {"type": "object"}
        },
        "required": ["task"]
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "answer": {"type": "string"},
          "reasoning": {"type": "string"}
        }
      },
      "max_timeout_ms": 120000
    }
  ],
  "endpoint": {
    "transport": "http",
    "uri": "https://mastro.example.com/mcp"
  },
  "tags": ["reasoning", "planning"],
  "trust_tier": "org"
}
```

### GET /mcp/list_agents

List all registered agents.

**Request:**
```bash
GET /mcp/list_agents
Authorization: Bearer <psk-or-token>
```

**Response:**
```json
{
  "agents": [
    {
      "agent_id": "percy",
      "display_name": "Percy",
      "version": "1.2.0",
      "status": "online",
      "capabilities": [...],
      "tags": ["planner", "reasoning"],
      "trust_tier": "org"
    }
  ],
  "count": 1
}
```

### GET /mcp/list_tools

List all available tools (built-in + agent capabilities).

**Request:**
```bash
GET /mcp/list_tools
Authorization: Bearer <psk-or-token>
```

**Response:**
```json
{
  "tools": [
    {
      "tool_id": "io.read_file",
      "provider": "builtin",
      "category": "io",
      "available": true
    },
    {
      "tool_id": "agent.percy.reason",
      "provider": "agent",
      "category": "agent:percy",
      "agent_id": "percy",
      "capability": "reason",
      "streaming": true
    }
  ],
  "count": 25
}
```

### GET /mcp/list_topics

List available Pub/Sub topics.

**Request:**
```bash
GET /mcp/list_topics
Authorization: Bearer <psk-or-token>
```

**Response:**
```json
{
  "topics": ["shared:events", "shared:insights", "system:alerts"],
  "count": 3
}
```

### GET /mcp/health

Health check endpoint.

**Request:**
```bash
GET /mcp/health
Authorization: Bearer <psk-or-token>
```

**Response:**
```json
{
  "ok": true,
  "status": "healthy",
  "registry": "ok",
  "runtimes": {
    "online": 4,
    "offline": 1,
    "degraded": 0
  },
  "version": "af-mcp-0.1",
  "uptime_seconds": 3600
}
```

### GET /mcp/metrics

Prometheus metrics.

**Request:**
```bash
GET /mcp/metrics
Authorization: Bearer <psk-or-token>
```

### GET /mcp/agent/{agent_id}

Get specific agent details.

**Request:**
```bash
GET /mcp/agent/percy
Authorization: Bearer <psk-or-token>
```

---

## Tool Calls

### Available Built-in Tools

| Tool ID | Capability | Description | Parameters |
|---------|------------|-------------|------------|
| `io.read_file` | `read` | Read file contents | `path`, `max_lines` |
| `io.write_file` | `write` | Write to file | `path`, `content`, `append` |
| `io.list_directory` | `list` | List directory | `path`, `recursive`, `pattern` |
| `io.search_files` | `search` | Search files | `path`, `pattern`, `recursive` |
| `web.http_request` | `request` | HTTP requests | `url`, `method`, `headers`, `body` |
| `web.fetch_page` | `fetch` | Extract web page | `url`, `extract_text` |
| `web.parse_url` | `parse` | Parse URL | `url` |
| `math.calculate` | `eval` | Safe math eval | `expression` |
| `math.statistics` | `stats` | Statistics | `values` |
| `text.regex` | `match` | Regex matching | `text`, `pattern` |
| `text.transform` | `transform` | Text transform | `text`, `operation`, `params` |
| `text.diff` | `diff` | Text diff | `text1`, `text2` |
| `system.execute` | `exec` | Shell commands | `command`, `timeout`, `env` |
| `system.env` | `get` | Get env vars | `key`, `default` |
| `system.datetime` | `now` | Get datetime | `format` |
| `data.json` | `parse` | Parse JSON | `json_string`, `validate` |
| `data.csv` | `parse` | Parse CSV | `csv_string`, `delimiter` |
| `data.validate` | `validate` | Validate data | `data`, `schema` |
| `security.hash` | `hash` | Hash data | `data`, `algorithm` |
| `security.base64` | `encode/decode` | Base64 ops | `data`, `operation` |
| `encode.url` | `encode/decode` | URL encoding | `string`, `operation` |
| `docs.markdown` | `render` | Render markdown | `content` |

### Calling a Tool

**Request:**
```json
POST /mcp/call
Authorization: Bearer your-secret-key
Content-Type: application/json

{
  "name": "fabric.tool.call",
  "arguments": {
    "tool_id": "web.http_request",
    "capability": "request",
    "parameters": {
      "url": "https://api.github.com/users/octocat",
      "method": "GET",
      "headers": {
        "Accept": "application/vnd.github.v3+json"
      }
    }
  }
}
```

**Response:**
```json
{
  "ok": true,
  "result": {
    "status": 200,
    "headers": {...},
    "body": {...}
  },
  "trace": {
    "trace_id": "550e8400-e29b-41d4-a716-446655440000",
    "span_id": "7f3a8b2c-1d9e-4f5a-b3c2-9e8d7c6b5a4f"
  }
}
```

### Error Response

```json
{
  "ok": false,
  "error": {
    "code": "EXECUTION_ERROR",
    "message": "Failed to execute tool",
    "details": {...}
  },
  "trace": {
    "trace_id": "...",
    "span_id": "..."
  }
}
```

---

## Agent Communication

### Calling Another Agent

**Request:**
```json
POST /mcp/call
Authorization: Bearer your-secret-key
Content-Type: application/json

{
  "name": "fabric.call",
  "arguments": {
    "agent_id": "percy",
    "capability": "reason",
    "task": "Analyze the pros and cons of microservices architecture",
    "context": {
      "domain": "software architecture",
      "depth": "detailed"
    },
    "stream": false,
    "timeout_ms": 60000
  }
}
```

**Response:**
```json
{
  "ok": true,
  "result": {
    "answer": "Microservices offer...",
    "reasoning_steps": [...],
    "citations": [...]
  },
  "trace": {
    "trace_id": "550e8400-e29b-41d4-a716-446655440000",
    "span_id": "7f3a8b2c-1d9e-4f5a-b3c2-9e8d7c6b5a4f"
  }
}
```

### Streaming Call

**Request:**
```json
{
  "name": "fabric.call",
  "arguments": {
    "agent_id": "percy",
    "capability": "reason",
    "task": "Explain quantum computing",
    "stream": true
  }
}
```

**Response (SSE stream):**
```
data: {"event":"status","data":{"status":"running","trace":{"trace_id":"..."}}}

data: {"event":"token","data":{"text":"Quantum computing is","trace":{"trace_id":"..."}}}

data: {"event":"token","data":{"text":" based on qubits","trace":{"trace_id":"..."}}}

data: {"event":"final","data":{"ok":true,"result":{"answer":"..."},"trace":{"trace_id":"..."}}}
```

---

## Async Messaging

### Overview

Async messaging uses **Redis Streams** for persistent task queues and **Pub/Sub** for real-time notifications.

**Requires:** Redis ACL configured with appropriate permissions

### Message Flow

```
Mastro → Redis Stream (agent:percy:inbox) → Percy reads from stream
              ↓
        Redis Pub/Sub (agent.percy.new_message) → Percy gets notified
```

### Sending Async Task

**Via HTTP:**
```json
POST /mcp/call
Authorization: Bearer your-secret-key
Content-Type: application/json

{
  "name": "fabric.message.send",
  "arguments": {
    "from_agent": "mastro",
    "to_agent": "percy",
    "message_type": "task",
    "payload": {
      "task_type": "reason",
      "task": "Analyze this architecture",
      "context": {...}
    },
    "priority": "normal",
    "reply_to": "agent:mastro:results"
  }
}
```

**Response:**
```json
{
  "ok": true,
  "result": {
    "message_id": "msg:uuid-here",
    "status": "queued",
    "stream_id": "1700000000000-0",
    "timestamp": "2026-02-13T10:00:00Z"
  },
  "trace": {...}
}
```

### Receiving Messages

**Via HTTP:**
```json
POST /mcp/call
Authorization: Bearer your-secret-key
Content-Type: application/json

{
  "name": "fabric.message.receive",
  "arguments": {
    "agent_id": "mastro",
    "count": 10,
    "block_ms": 5000
  }
}
```

**Via Direct Redis (requires ACL):**
```python
import redis.asyncio as redis

r = redis.from_url("redis://fabric-host:6379", decode_responses=True)

# Read from stream
entries = await r.xread(
    streams={"agent:mastro:inbox": "0"},
    count=10,
    block=5000
)

for stream, messages in entries:
    for msg_id, data in messages:
        content = json.loads(data["data"])
        print(f"Message: {content}")
```

### Publishing Events

```json
POST /mcp/call
Authorization: Bearer your-secret-key
Content-Type: application/json

{
  "name": "fabric.message.publish",
  "arguments": {
    "topic": "shared:insights",
    "message": {
      "type": "discovery",
      "data": {...}
    },
    "from_agent": "mastro"
  }
}
```

**Response:**
```json
{
  "ok": true,
  "result": {
    "topic": "shared:insights",
    "recipients": 3,
    "published": true
  },
  "trace": {...}
}
```

---

## Python Client Implementation

### Complete Fabric Client

```python
# fabric_client.py
import asyncio
import aiohttp
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum


class MessagePriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class FabricConfig:
    base_url: str = "https://fabric.perceptor.us"
    auth_token: str = ""
    timeout_ms: int = 60000
    master_secret: str = ""


class FabricError(Exception):
    def __init__(self, code: str, message: str, details: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"[{code}] {message}")


class FabricClient:
    """
    Complete Fabric MCP client for:
    - Tool calls
    - Agent communication
    - Async messaging (requires Redis ACL)
    """
    
    def __init__(self, config: Optional[FabricConfig] = None):
        self.config = config or FabricConfig()
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        await self.open()
        return self
    
    async def __aexit__(self, *args):
        await self.close()
    
    async def open(self):
        """Open HTTP session"""
        timeout = aiohttp.ClientTimeout(total=self.config.timeout_ms / 1000)
        self._session = aiohttp.ClientSession(timeout=timeout)
    
    async def close(self):
        """Close HTTP session"""
        if self._session:
            await self._session.close()
            self._session = None
    
    def _headers(self) -> Dict[str, str]:
        """Build auth headers"""
        headers = {"Content-Type": "application/json"}
        if self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"
        return headers
    
    async def _call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Make MCP call"""
        if not self._session:
            raise RuntimeError("Client not opened. Use 'async with' or call open()")
        
        url = f"{self.config.base_url}/mcp/call"
        payload = {"name": name, "arguments": arguments}
        
        async with self._session.post(
            url, json=payload, headers=self._headers()
        ) as response:
            response.raise_for_status()
            result = await response.json()
            
            if not result.get("ok"):
                error = result.get("error", {})
                raise FabricError(
                    error.get("code", "UNKNOWN"),
                    error.get("message", "Unknown error"),
                    error.get("details")
                )
            
            return result.get("result")
    
    # === Tool Calls ===
    
    async def call_tool(
        self,
        tool_id: str,
        capability: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call any Fabric tool"""
        return await self._call("fabric.tool.call", {
            "tool_id": tool_id,
            "capability": capability,
            "parameters": parameters
        })
    
    async def list_tools(
        self,
        category: Optional[str] = None,
        provider: Optional[str] = None
    ) -> Dict[str, Any]:
        """List available tools"""
        args = {}
        if category:
            args["category"] = category
        if provider:
            args["provider"] = provider
        return await self._call("fabric.tool.list", args)
    
    async def describe_tool(self, tool_id: str) -> Dict[str, Any]:
        """Get tool details"""
        return await self._call("fabric.tool.describe", {"tool_id": tool_id})
    
    # === Convenience Methods ===
    
    async def search_web(
        self,
        query: str,
        max_results: int = 5,
        recency_days: int = 7
    ) -> Dict[str, Any]:
        """Web search"""
        return await self.call_tool(
            "web.brave_search", "search",
            {"query": query, "max_results": max_results, "recency_days": recency_days}
        )
    
    async def read_file(self, path: str, max_lines: Optional[int] = None) -> str:
        """Read file"""
        params = {"path": path}
        if max_lines:
            params["max_lines"] = max_lines
        result = await self.call_tool("io.read_file", "read", params)
        return result.get("content", "")
    
    async def write_file(
        self,
        path: str,
        content: str,
        append: bool = False
    ) -> Dict[str, Any]:
        """Write file"""
        return await self.call_tool(
            "io.write_file", "write",
            {"path": path, "content": content, "append": append}
        )
    
    async def http_request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict] = None,
        body: Optional[str] = None
    ) -> Dict[str, Any]:
        """HTTP request"""
        params = {"url": url, "method": method}
        if headers:
            params["headers"] = headers
        if body:
            params["body"] = body
        return await self.call_tool("web.http_request", "request", params)
    
    async def calculate(self, expression: str) -> float math"""
        result = await self.call:
        """Calculate_tool("math.calculate", "eval", {"expression": expression})
        return result.get("result")
    
    # === Agent Communication ===
    
    async def list_agents(
        self,
        capability: Optional[str] = None,
        tag: Optional[str] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """List registered agents"""
        args = {}
        if capability:
            args["capability"] = capability
        if tag:
            args["tag"] = tag
        if status:
            args["status"] = status
        return await self._call("fabric.agent.list", args)
    
    async def describe_agent(self, agent_id: str) -> Dict[str, Any]:
        """Get agent details"""
        return await self._call("fabric.agent.describe", {"agent_id": agent_id})
    
    async def call_agent(
        self,
        agent_id: str,
        capability: str,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        timeout_ms: Optional[int] = None
    ) -> Dict[str, Any]:
        """Call another agent"""
        args = {
            "agent_id": agent_id,
            "capability": capability,
            "task": task
        }
        if context:
            args["context"] = context
        if stream:
            args["stream"] = True
        if timeout_ms:
            args["timeout_ms"] = timeout_ms
        return await self._call("fabric.call", args)
    
    # === Async Messaging ===
    
    async def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message_type: str,
        payload: Dict[str, Any],
        priority: str = "normal",
        reply_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send async message to agent"""
        return await self._call("fabric.message.send", {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "message_type": message_type,
            "payload": payload,
            "priority": priority,
            "reply_to": reply_to
        })
    
    async def send_task(
        self,
        from_agent: str,
        to_agent: str,
        task_type: str,
        payload: Dict[str, Any],
        priority: str = "normal"
    ) -> Dict[str, Any]:
        """Send task to agent"""
        return await self.send_message(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type="task",
            payload={"task_type": task_type, **payload},
            priority=priority
        )
    
    async def receive_messages(
        self,
        agent_id: str,
        count: int = 10,
        block_ms: int = 5000
    ) -> Dict[str, Any]:
        """Receive messages"""
        return await self._call("fabric.message.receive", {
            "agent_id": agent_id,
            "count": count,
            "block_ms": block_ms
        })
    
    async def acknowledge(
        self,
        agent_id: str,
        message_ids: List[str]
    ) -> Dict[str, Any]:
        """Acknowledge message processing"""
        return await self._call("fabric.message.acknowledge", {
            "agent_id": agent_id,
            "message_ids": message_ids
        })
    
    async def publish(
        self,
        topic: str,
        message: Dict[str, Any],
        from_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """Publish to topic"""
        args = {"topic": topic, "message": message}
        if from_agent:
            args["from_agent"] = from_agent
        return await self._call("fabric.message.publish", args)
    
    async def queue_status(self, agent_id: str) -> Dict[str, Any]:
        """Get queue status"""
        return await self._call("fabric.message.queue_status", {
            "agent_id": agent_id
        })
    
    # === Health & Info ===
    
    async def health_check(self) -> Dict[str, Any]:
        """Check server health"""
        url = f"{self.config.base_url}/health"
        async with self._session.get(url) as response:
            return await response.json()
    
    async def get_metrics(self) -> str:
        """Get Prometheus metrics"""
        url = f"{self.config.base_url}/mcp/metrics"
        async with self._session.get(url, headers=self._headers()) as response:
            return await response.text()
```

### Usage Examples

```python
import asyncio
from fabric_client import FabricClient, FabricConfig


async def main():
    # Create client
    config = FabricConfig(
        base_url="https://fabric.perceptor.us",
        auth_token="your-psk-or-token"
    )
    
    async with FabricClient(config) as fabric:
        # Check health
        health = await fabric.health_check()
        print(f"Fabric status: {health['status']}")
        
        # List tools
        tools = await fabric.list_tools()
        print(f"Available tools: {tools['count']}")
        
        # Call a tool
        result = await fabric.calculate("(2 + 3) * 4")
        print(f"Calculation result: {result}")
        
        # List agents
        agents = await fabric.list_agents()
        print(f"Online agents: {len(agents['agents'])}")
        
        # Call another agent
        result = await fabric.call_agent(
            agent_id="percy",
            capability="reason",
            task="What is the capital of France?"
        )
        print(f"Percy says: {result['answer']}")
        
        # Async messaging
        await fabric.send_task(
            from_agent="mastro",
            to_agent="percy",
            task_type="reason",
            payload={"task": "Analyze this data"}
        )


asyncio.run(main())
```

---

## Agent Registration

### Register Your Agent

```json
POST /mcp/register_agent
Authorization: Bearer <master-secret>
Content-Type: application/json

{
  "agent_id": "mastro",
  "display_name": "Mastro Agent",
  "version": "1.0.0",
  "description": "Specialized reasoning and planning agent",
  "capabilities": [
    {
      "name": "reason",
      "description": "Complex reasoning and analysis",
      "streaming": true,
      "modalities": ["text"],
      "input_schema": {
        "type": "object",
        "properties": {
          "task": {"type": "string"},
          "context": {"type": "object"}
        },
        "required": ["task"]
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "answer": {"type": "string"},
          "reasoning": {"type": "string"}
        }
      },
      "max_timeout_ms": 120000
    },
    {
      "name": "plan",
      "description": "Create action plans",
      "streaming": false,
      "input_schema": {
        "type": "object",
        "properties": {
          "goal": {"type": "string"},
          "constraints": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["goal"]
      }
    }
  ],
  "endpoint": {
    "transport": "http",
    "uri": "https://mastro.example.com/mcp"
  },
  "tags": ["reasoning", "planning", "analysis"],
  "trust_tier": "org"
}
```

### Response

```json
{
  "ok": true,
  "result": {
    "registered": true,
    "agent_id": "mastro"
  }
}
```

### Your MCP Server Requirements

When other agents call you, your agent must implement an MCP server:

**Your server must handle:**
- `GET /health` - Health checks
- `POST /mcp/call` - Capability calls
- Streaming responses if you declare `streaming: true`

---

## ACL Security

### What ACL Is For

ACL (Access Control List) in Redis controls **Redis-level permissions**:

1. **Stream Access**: Which agent can read/write which streams
2. **Pub/Sub Channels**: Which agent can publish/subscribe to which channels
3. **Command Permissions**: Which Redis commands are allowed per user

### ACL Components

| Component | Purpose | Example |
|-----------|---------|---------|
| `~key_pattern` | Stream/key access | `~agent:mastro:*` |
| `&channel_pattern` | Pub/Sub access | `&shared:*` |
| `+@category` | Command category | `+@stream`, `+@pubsub` |
| `-@category` | Deny commands | `-@dangerous` |

### Example ACL for Mastro

```acl
# Mastro Agent
user mastro on >mastro_secret123 ~agent:mastro:* ~shared:* +@stream +@pubsub +@read &shared:* &agent.mastro:*
```

**This means Mastro can:**
- Read/write streams: `agent:mastro:*`
- Read shared state: `shared:*`
- Use stream commands: XADD, XREAD, XREADGROUP, XACK
- Use pub/sub: PUBLISH, SUBSCRIBE
- Access channels: `shared:*`, `agent.mastro:*`

### ACL for Different Scenarios

**Development (minimal):**
```
user default off on nopass ~* +@all
```

**Production Agent:**
```
user mastro on >secure_secret ~agent:mastro:* ~shared:results +@stream +@pubsub +@read &shared:* &agent.mastro:*
```

**Fabric MCP Server (admin):**
```
user fabric_mcp on >mcp_secret ~agent:* +@all &*
```

### Setting Up ACL

1. Edit `/opt/redis/users.acl` on your Redis host
2. Restart Redis: `systemctl restart redis`
3. Verify: `redis-cli ACL LIST`

---

## Environment Setup

### Configuration File

```yaml
# fabric_config.yaml for Mastro
fabric:
  base_url: "https://fabric.perceptor.us"
  auth_token: "${FABRIC_AUTH_TOKEN}"
  timeout_ms: 60000

redis:
  url: "redis://localhost:6379"  # Or private IP in production
  acl:
    user: "mastro"
    password: "${REDIS_PASSWORD}"

passport:
  enabled: true
  url: "https://passport.aetherpro.us"
  realm: "fabric"
  client_id: "mastro-agent"
  client_secret: "${PASSPORT_CLIENT_SECRET}"

agent:
  id: "mastro"
  display_name: "Mastro Agent"
  endpoint: "https://mastro.example.com/mcp"
```

### Environment Variables

```bash
# .env
FABRIC_BASE_URL=https://fabric.perceptor.us
FABRIC_AUTH_TOKEN=your-psk-or-token
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=your-redis-password
PASSPORT_CLIENT_SECRET=your-passport-secret
MASTER_SECRET=fabric-master-secret-for-registration
```

### Dependencies

```txt
# requirements.txt
aiohttp>=3.9.0
python-dotenv>=1.0.0
```

---

## Quick Reference

### Common Calls

```python
# Initialize
async with FabricClient(config) as fabric:
    # Tools
    await fabric.list_tools()
    await fabric.call_tool("io.read_file", "read", {"path": "/file.txt"})
    
    # Agents
    await fabric.list_agents()
    await fabric.call_agent("percy", "reason", "Analyze this")
    
    # Async messaging
    await fabric.send_task("mastro", "percy", "reason", {"task": "..."})
    await fabric.receive_messages("mastro")
    await fabric.publish("shared:events", {"type": "update"})
```

### Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| `AGENT_OFFLINE` | Agent not responding | Retry later |
| `AGENT_NOT_FOUND` | Unknown agent ID | Check registry |
| `CAPABILITY_NOT_FOUND` | Agent lacks capability | Use different agent |
| `AUTH_DENIED` | Invalid credentials | Check token |
| `AUTH_EXPIRED` | Token expired | Refresh token |
| `TIMEOUT` | Operation timed out | Retry with longer timeout |
| `BAD_INPUT` | Invalid parameters | Fix request |
| `UPSTREAM_ERROR` | Agent error | Check agent logs |

---

## Support

- Documentation: `fabric/README.md`
- Architecture: `fabric/architecture.md`
- Tools Inventory: `fabric/TOOLS_INVENTORY.md`
- Legacy Specs: `fabric/INTEGRATION_SPEC_FOR_*.md`

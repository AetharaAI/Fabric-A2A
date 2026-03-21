# Fabric MCP Integration Spec

## For: Your New Agent (First Fabric Consumer)

---

## Overview

**Fabric MCP Server** is an **Agent-to-Agent (A2A)** communication gateway that also provides a universal tool inventory. This spec covers how YOUR agent connects to Fabric as a client.

### Key Points

1. **A2A is Core**: Fabric's primary purpose is routing messages between agents
2. **Tools are Bonus**: Built-in tools (web search, file ops, etc.) are secondary
3. **Your Agent = Client**: You call Fabric, not the other way around (for now)
4. **Future**: You can register YOUR agent in Fabric's `agents.yaml` so other agents can call you

---

## Connection Details

```yaml
# fabric_config.yaml for your agent
fabric:
  base_url: "https://fabric.perceptor.us"
  auth_token: "dev-shared-secret"
  timeout_ms: 60000
  
  # MCP endpoint
  mcp_endpoint: "/mcp/call"
  
  # Health check endpoint
  health_endpoint: "/health"
```

---

## Part 1: Calling Built-in Tools

### Available Tools

| Tool ID | Capability | What It Does | Key Params |
|---------|------------|--------------|------------|
| `web.brave_search` | `search` | Live web search | `query`, `max_results`, `recency_days` |
| `io.read_file` | `read` | Read file contents | `path`, `max_lines` |
| `io.write_file` | `write` | Write to file | `path`, `content`, `append` |
| `io.list_directory` | `list` | List files | `path`, `recursive`, `pattern` |
| `web.http_request` | `request` | HTTP calls | `url`, `method`, `headers`, `body` |
| `web.fetch_page` | `fetch` | Extract web page text | `url`, `extract_text` |
| `math.calculate` | `eval` | Safe math eval | `expression` |
| `text.regex` | `match` | Regex matching | `text`, `pattern` |
| `system.execute` | `exec` | Run shell commands | `command`, `timeout` |

### Request Format

```bash
POST https://fabric.perceptor.us/mcp/call
Content-Type: application/json
Authorization: Bearer dev-shared-secret
```

```json
{
  "name": "fabric.tool.call",
  "arguments": {
    "tool_id": "web.brave_search",
    "capability": "search",
    "parameters": {
      "query": "AetherPro Fabric MCP",
      "recency_days": 7,
      "max_results": 5
    }
  }
}
```

### Response Format

```json
{
  "ok": true,
  "result": {
    "provider": "brave",
    "query": "AetherPro Fabric MCP",
    "results": [
      {
        "title": "...",
        "url": "...",
        "snippet": "...",
        "age_days": 0
      }
    ]
  },
  "error": null,
  "trace": {
    "trace_id": "...",
    "span_id": "..."
  }
}
```

### Error Format

```json
{
  "ok": false,
  "result": null,
  "error": {
    "code": "EXECUTION_ERROR",
    "message": "BRAVE_API_KEY not set"
  },
  "trace": {...}
}
```

---

## Part 2: Implementation (Python Example)

### FabricClient Class

```python
# fabric_client.py
import os
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
    """Client for Fabric MCP Server"""
    
    def __init__(self, config: Optional[FabricConfig] = None):
        self.config = config or FabricConfig()
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()
            self._session = None
    
    def _get_session(self) -> aiohttp.ClientSession:
        if not self._session:
            raise RuntimeError("Client not opened. Use 'async with' or call open()")
        return self._session
    
    async def open(self):
        """Open session manually if not using 'async with'"""
        self._session = aiohttp.ClientSession()
    
    async def close(self):
        """Close session manually"""
        if self._session:
            await self._session.close()
            self._session = None
    
    async def call_tool(
        self, 
        tool_id: str, 
        capability: str, 
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call a Fabric tool
        
        Args:
            tool_id: e.g., "web.brave_search", "io.read_file"
            capability: e.g., "search", "read", "write"
            parameters: Tool-specific parameters
            
        Returns:
            The result.data field on success
            
        Raises:
            FabricError: On tool execution error
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
        
        async with self._get_session().post(
            url, 
            json=payload, 
            headers=headers,
            timeout=timeout
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
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Fabric server health"""
        url = f"{self.config.base_url}/health"
        
        async with self._get_session().get(url) as response:
            response.raise_for_status()
            return await response.json()
    
    # === Convenience methods for common tools ===
    
    async def search_web(
        self, 
        query: str, 
        max_results: int = 5,
        recency_days: int = 7
    ) -> Dict[str, Any]:
        """Search the web using Brave"""
        return await self.call_tool(
            "web.brave_search",
            "search",
            {
                "query": query,
                "max_results": max_results,
                "recency_days": recency_days
            }
        )
    
    async def read_file(self, path: str, max_lines: Optional[int] = None) -> str:
        """Read a file"""
        result = await self.call_tool(
            "io.read_file",
            "read",
            {"path": path, "max_lines": max_lines}
        )
        return result.get("content", "")
    
    async def write_file(self, path: str, content: str, append: bool = False) -> Dict[str, Any]:
        """Write to a file"""
        return await self.call_tool(
            "io.write_file",
            "write",
            {"path": path, "content": content, "append": append}
        )
    
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
            {
                "url": url,
                "method": method,
                "headers": headers,
                "body": body
            }
        )


class FabricError(Exception):
    """Fabric MCP error"""
    def __init__(self, code: str, message: str, details: Optional[Dict] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(f"[{code}] {message}")
```

### Usage Example

```python
# example_usage.py
import asyncio
from fabric_client import FabricClient, FabricConfig


async def main():
    # Method 1: Using async with (recommended)
    async with FabricClient() as fabric:
        # Search the web
        results = await fabric.search_web("AetherPro AI agents")
        print(f"Found {len(results['results'])} results")
        
        for r in results['results'][:3]:
            print(f"- {r['title']}: {r['url']}")
        
        # Read a file
        content = await fabric.read_file("/path/to/file.txt")
        print(f"File content: {content[:500]}")
    
    # Method 2: Manual session management
    fabric = FabricClient(FabricConfig(
        base_url="https://fabric.perceptor.us",
        auth_token="dev-shared-secret"
    ))
    
    await fabric.open()
    try:
        result = await fabric.call_tool(
            "math.calculate",
            "eval",
            {"expression": "(2 + 3) * 4"}
        )
        print(f"Result: {result['result']}")
    finally:
        await fabric.close()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Part 3: Environment Setup

```bash
# .env file for your agent
FABRIC_BASE_URL=https://fabric.perceptor.us
FABRIC_AUTH_TOKEN=dev-shared-secret

# Optional: Override timeouts
FABRIC_TIMEOUT_MS=60000
```

```python
# config.py
import os
from fabric_client import FabricConfig


def load_config() -> FabricConfig:
    return FabricConfig(
        base_url=os.getenv("FABRIC_BASE_URL", "https://fabric.perceptor.us"),
        auth_token=os.getenv("FABRIC_AUTH_TOKEN", "dev-shared-secret"),
        timeout_ms=int(os.getenv("FABRIC_TIMEOUT_MS", "60000"))
    )
```

---

## Part 4: Retry & Error Handling

```python
# enhanced_client.py
import asyncio
from typing import TypeVar, Callable
from fabric_client import FabricClient, FabricError

T = TypeVar('T')


class ResilientFabricClient(FabricClient):
    """Fabric client with retry logic"""
    
    async def call_with_retry(
        self,
        operation: Callable[..., T],
        max_retries: int = 3,
        base_delay: float = 1.0,
        **kwargs
    ) -> T:
        """Call an operation with exponential backoff retry"""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return await operation(**kwargs)
            except FabricError as e:
                # Don't retry on auth errors
                if e.code in ("AUTH_DENIED", "AUTH_INVALID", "BAD_INPUT"):
                    raise
                    
                last_error = e
                delay = base_delay * (2 ** attempt)
                
                print(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
        
        raise last_error
    
    async def search_web_safe(self, query: str, **kwargs) -> Dict[str, Any]:
        """Search with retry"""
        return await self.call_with_retry(
            self.search_web,
            query=query,
            **kwargs
        )
```

---

## Part 5: Future - Registering Your Agent

Once your agent is ready, you can register it in Fabric so OTHER agents can call YOU:

```yaml
# In Fabric's agents.yaml
agents:
  - agent_id: your_agent_name
    display_name: "Your Agent Display Name"
    version: "1.0.0"
    description: "What your agent does"
    runtime: mcp
    endpoint:
      transport: http
      uri: https://your-agent-host/mcp
    capabilities:
      - name: your_capability
        description: "What this capability does"
        input_schema:
          type: object
          properties:
            param1:
              type: string
          required: [param1]
        max_timeout_ms: 60000
```

Then other agents can call you via:

```python
# Another agent calling YOUR agent through Fabric
result = await fabric.call_tool(
    "agent.your_agent_name.your_capability",
    "your_capability",
    {"param1": "value"}
)
```

---

## Quick Reference Card

```python
# Import
from fabric_client import FabricClient

# Create client
fabric = FabricClient()

# Use it
async with fabric:
    # Web search
    results = await fabric.search_web("query")
    
    # File operations  
    content = await fabric.read_file("/path")
    await fabric.write_file("/path", "content")
    
    # HTTP requests
    response = await fabric.http_request("https://api.example.com")
    
    # Math
    result = await fabric.call_tool("math.calculate", "eval", {"expression": "1+1"})
    
    # Regex
    matches = await fabric.call_tool("text.regex", "match", {
        "text": "hello world",
        "pattern": "hello (\w+)"
    })
```

---

**Copy this entire file to your other repo and tell me to implement the Fabric client!**

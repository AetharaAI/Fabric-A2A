"""
Fabric A2A Python SDK
=====================

A lightweight, production-grade Python client for the Fabric A2A
agent-to-agent communication framework.

Usage:
    pip install fabric-a2a  # (future PyPI package)

    from fabric_a2a_sdk import FabricClient

    client = FabricClient(
        base_url="https://fabric.perceptor.us",
        api_key="your-master-secret"
    )

    # Register your agent
    client.register_agent(
        agent_id="my-agent",
        display_name="My Agent",
        capabilities=[{"name": "process", "description": "Process data"}],
        endpoint="http://localhost:9000/mcp"
    )

    # Send a task to another agent
    result = client.call_agent(
        agent_id="aether-agent",
        capability="reason",
        task="Analyze this data set for anomalies"
    )

    # Send async message
    client.send_message(
        from_agent="my-agent",
        to_agent="aether-agent",
        payload={"task_type": "analyze", "data": [1, 2, 3]}
    )
"""

from __future__ import annotations

import json
import time
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional
from urllib.parse import urljoin

try:
    import httpx
    _HTTP_CLIENT = "httpx"
except ImportError:
    import urllib.request
    import urllib.error
    _HTTP_CLIENT = "urllib"

__version__ = "0.1.0"
__all__ = [
    "FabricClient",
    "FabricError",
    "AgentCapability",
    "AgentInfo",
    "Message",
    "MessagePriority",
    "ToolResult",
]

logger = logging.getLogger("fabric_a2a_sdk")


# =============================================================================
# Exceptions
# =============================================================================

class FabricError(Exception):
    """Base exception for Fabric SDK errors."""
    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class FabricConnectionError(FabricError):
    """Raised when the Fabric server is unreachable."""
    pass


class FabricAuthError(FabricError):
    """Raised on 401/403 responses."""
    pass


class FabricNotFoundError(FabricError):
    """Raised when an agent or resource is not found."""
    pass


class FabricTimeoutError(FabricError):
    """Raised when a request or task times out."""
    pass


# =============================================================================
# Data Models
# =============================================================================

class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AgentCapability:
    name: str
    description: str

    def to_dict(self) -> dict:
        return {"name": self.name, "description": self.description}


@dataclass
class AgentEndpoint:
    transport: str = "http"
    uri: str = ""

    def to_dict(self) -> dict:
        return {"transport": self.transport, "uri": self.uri}


@dataclass
class AgentInfo:
    agent_id: str
    display_name: str
    version: str = "1.0.0"
    capabilities: list[AgentCapability] = field(default_factory=list)
    endpoint: AgentEndpoint | None = None
    status: str = "unknown"
    last_seen: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> AgentInfo:
        caps = [
            AgentCapability(**c) if isinstance(c, dict) else c
            for c in data.get("capabilities", [])
        ]
        endpoint = None
        if "endpoint" in data and data["endpoint"]:
            endpoint = AgentEndpoint(**data["endpoint"]) if isinstance(data["endpoint"], dict) else data["endpoint"]
        return cls(
            agent_id=data.get("agent_id", ""),
            display_name=data.get("display_name", ""),
            version=data.get("version", "1.0.0"),
            capabilities=caps,
            endpoint=endpoint,
            status=data.get("status", "unknown"),
            last_seen=data.get("last_seen"),
        )


@dataclass
class Message:
    message_id: str
    from_agent: str
    to_agent: str
    message_type: str
    payload: dict
    timestamp: str | None = None
    priority: str = "normal"

    @classmethod
    def from_dict(cls, data: dict) -> Message:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ToolResult:
    tool_id: str
    success: bool
    result: Any = None
    error: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> ToolResult:
        return cls(
            tool_id=data.get("tool_id", ""),
            success=data.get("success", False),
            result=data.get("result"),
            error=data.get("error"),
        )


@dataclass
class CallResult:
    agent_id: str
    capability: str
    success: bool
    result: Any = None
    error: str | None = None
    duration_ms: float = 0

    @classmethod
    def from_dict(cls, data: dict) -> CallResult:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# =============================================================================
# HTTP Transport Layer (supports httpx or stdlib)
# =============================================================================

class _HttpTransport:
    """Abstraction over httpx (preferred) or urllib (fallback)."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"fabric-a2a-sdk/{__version__}",
        }

        if _HTTP_CLIENT == "httpx":
            self._client = httpx.Client(
                base_url=self.base_url,
                headers=self._headers,
                timeout=timeout,
            )
        else:
            self._client = None

    def get(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        logger.debug(f"GET {url}")

        if _HTTP_CLIENT == "httpx":
            try:
                resp = self._client.get(path)
                return self._handle_httpx_response(resp)
            except httpx.ConnectError as e:
                raise FabricConnectionError(f"Cannot connect to {url}: {e}")
            except httpx.TimeoutException as e:
                raise FabricTimeoutError(f"Request timed out: {e}")
        else:
            return self._urllib_request("GET", url)

    def post(self, path: str, data: dict) -> dict:
        url = f"{self.base_url}{path}"
        logger.debug(f"POST {url} body={json.dumps(data)[:200]}")

        if _HTTP_CLIENT == "httpx":
            try:
                resp = self._client.post(path, json=data)
                return self._handle_httpx_response(resp)
            except httpx.ConnectError as e:
                raise FabricConnectionError(f"Cannot connect to {url}: {e}")
            except httpx.TimeoutException as e:
                raise FabricTimeoutError(f"Request timed out: {e}")
        else:
            return self._urllib_request("POST", url, data)

    def _handle_httpx_response(self, resp: httpx.Response) -> dict:
        if resp.status_code == 401 or resp.status_code == 403:
            raise FabricAuthError(
                f"Authentication failed (HTTP {resp.status_code})",
                status_code=resp.status_code,
            )
        if resp.status_code == 404:
            raise FabricNotFoundError(
                f"Resource not found (HTTP 404)",
                status_code=404,
            )
        if resp.status_code >= 400:
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            raise FabricError(
                f"HTTP {resp.status_code}: {resp.text[:200]}",
                status_code=resp.status_code,
                response=body,
            )

        # Handle non-JSON responses (metrics, docs page, etc.)
        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            return resp.json()
        return {"_raw": resp.text, "_status": resp.status_code}

    def _urllib_request(self, method: str, url: str, data: dict | None = None) -> dict:
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=self._headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode()
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return {"_raw": raw, "_status": resp.status}
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise FabricAuthError(f"Auth failed (HTTP {e.code})", status_code=e.code)
            if e.code == 404:
                raise FabricNotFoundError("Not found", status_code=404)
            raise FabricError(f"HTTP {e.code}", status_code=e.code)
        except urllib.error.URLError as e:
            raise FabricConnectionError(f"Cannot connect: {e}")

    def close(self):
        if _HTTP_CLIENT == "httpx" and self._client:
            self._client.close()


# =============================================================================
# Main Client
# =============================================================================

class FabricClient:
    """
    Production-grade client for the Fabric A2A framework.

    Example:
        client = FabricClient("https://fabric.perceptor.us", "my-secret")

        # Register your agent
        client.register_agent(
            agent_id="my-agent",
            display_name="My Custom Agent",
            capabilities=[{"name": "analyze", "description": "Data analysis"}],
            endpoint="http://my-server:9000/mcp"
        )

        # Delegate a task
        result = client.call_agent("aether-agent", "reason", "Explain quantum computing")

        # Async messaging
        client.send_message("my-agent", "aether-agent", {"task_type": "review", "data": "..."})
        messages = client.receive_messages("my-agent", count=10)
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: str = "",
        timeout: float = 30.0,
    ):
        self._transport = _HttpTransport(base_url, api_key, timeout)
        self.base_url = base_url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        """Close the underlying HTTP connection."""
        self._transport.close()

    # ── Health & Status ───────────────────────────────────────────────────────

    def health(self) -> dict:
        """Check Fabric server health."""
        return self._transport.get("/health")

    def mcp_health(self) -> dict:
        """Check MCP server health."""
        return self._transport.get("/mcp/health")

    def metrics(self) -> str:
        """Get Prometheus metrics."""
        result = self._transport.get("/mcp/metrics")
        return result.get("_raw", str(result))

    # ── Agent Registry ────────────────────────────────────────────────────────

    def register_agent(
        self,
        agent_id: str,
        display_name: str,
        capabilities: list[dict | AgentCapability],
        endpoint: str | dict | AgentEndpoint = "",
        version: str = "1.0.0",
    ) -> dict:
        """
        Register an agent with the Fabric registry.

        Args:
            agent_id:      Unique identifier (e.g., "my-agent")
            display_name:  Human-readable name
            capabilities:  List of {"name": "...", "description": "..."} dicts
            endpoint:      URI string or {"transport": "http", "uri": "..."} dict
            version:       Semantic version string

        Returns:
            Registration confirmation dict
        """
        caps = [
            c.to_dict() if isinstance(c, AgentCapability) else c
            for c in capabilities
        ]

        if isinstance(endpoint, str):
            ep = {"transport": "http", "uri": endpoint}
        elif isinstance(endpoint, AgentEndpoint):
            ep = endpoint.to_dict()
        else:
            ep = endpoint

        payload = {
            "agent_id": agent_id,
            "display_name": display_name,
            "version": version,
            "capabilities": caps,
            "endpoint": ep,
        }

        return self._transport.post("/mcp/register_agent", payload)

    def list_agents(self) -> list[AgentInfo]:
        """List all registered agents."""
        result = self._transport.get("/mcp/list_agents")
        agents_data = result if isinstance(result, list) else result.get("agents", [])
        return [AgentInfo.from_dict(a) for a in agents_data]

    def get_agent(self, agent_id: str) -> AgentInfo:
        """Get details for a specific agent."""
        result = self._transport.get(f"/mcp/agent/{agent_id}")
        return AgentInfo.from_dict(result)

    # ── MCP Calls (Agent-to-Agent) ────────────────────────────────────────────

    def _mcp_call(self, name: str, arguments: dict) -> dict:
        """Low-level MCP call."""
        return self._transport.post("/mcp/call", {
            "name": name,
            "arguments": arguments,
        })

    def call_agent(
        self,
        agent_id: str,
        capability: str,
        task: str,
        context: dict | None = None,
        stream: bool = False,
        timeout_ms: int = 60000,
    ) -> CallResult:
        """
        Delegate a task to another agent via fabric.call.

        Args:
            agent_id:    Target agent ID
            capability:  Which capability to invoke
            task:        Natural language task description
            context:     Optional context dict
            stream:      Whether to stream the response
            timeout_ms:  Timeout in milliseconds

        Returns:
            CallResult with the agent's response
        """
        start = time.monotonic()
        result = self._mcp_call("fabric.call", {
            "agent_id": agent_id,
            "capability": capability,
            "task": task,
            "context": context or {},
            "stream": stream,
            "timeout_ms": timeout_ms,
        })
        elapsed = (time.monotonic() - start) * 1000

        return CallResult(
            agent_id=agent_id,
            capability=capability,
            success=result.get("success", True),
            result=result.get("result", result),
            error=result.get("error"),
            duration_ms=elapsed,
        )

    # ── Tools ─────────────────────────────────────────────────────────────────

    def list_tools(self) -> list[dict]:
        """List all available built-in tools."""
        result = self._transport.get("/mcp/list_tools")
        return result if isinstance(result, list) else result.get("tools", [])

    def call_tool(self, tool_id: str, capability: str = "", parameters: dict | None = None) -> ToolResult:
        """
        Execute a built-in tool.

        Args:
            tool_id:     Tool identifier (e.g., "math.calculate", "io.read_file")
            capability:  Tool capability to invoke
            parameters:  Tool-specific parameters

        Returns:
            ToolResult with success/failure and result data
        """
        result = self._mcp_call("fabric.tool.call", {
            "tool_id": tool_id,
            "capability": capability,
            "parameters": parameters or {},
        })
        return ToolResult.from_dict({
            "tool_id": tool_id,
            "success": result.get("success", True),
            "result": result.get("result", result),
            "error": result.get("error"),
        })

    # ── Async Messaging ───────────────────────────────────────────────────────

    def send_message(
        self,
        from_agent: str,
        to_agent: str,
        payload: dict,
        message_type: str = "task",
        priority: str | MessagePriority = MessagePriority.NORMAL,
    ) -> dict:
        """
        Send an async message from one agent to another.

        Args:
            from_agent:    Sender agent ID
            to_agent:      Recipient agent ID
            payload:       Message payload dict
            message_type:  Type of message ("task", "event", "response")
            priority:      Message priority level

        Returns:
            Confirmation dict with message_id
        """
        if isinstance(priority, MessagePriority):
            priority = priority.value

        return self._mcp_call("fabric.message.send", {
            "from_agent": from_agent,
            "to_agent": to_agent,
            "message_type": message_type,
            "payload": {**payload, "priority": priority},
        })

    def receive_messages(
        self,
        agent_id: str,
        count: int = 10,
        block_ms: int = 5000,
    ) -> list[Message]:
        """
        Receive messages from an agent's inbox.

        Args:
            agent_id:  Agent whose inbox to read
            count:     Max messages to retrieve
            block_ms:  How long to block waiting (ms)

        Returns:
            List of Message objects
        """
        result = self._mcp_call("fabric.message.receive", {
            "agent_id": agent_id,
            "count": count,
            "block_ms": block_ms,
        })
        messages_data = result if isinstance(result, list) else result.get("messages", [])
        return [Message.from_dict(m) for m in messages_data]

    # ── Pub/Sub Topics ────────────────────────────────────────────────────────

    def list_topics(self) -> list[dict]:
        """List active Pub/Sub topics."""
        result = self._transport.get("/mcp/list_topics")
        return result if isinstance(result, list) else result.get("topics", [])

    def publish(self, topic: str, data: dict) -> dict:
        """Publish an event to a Pub/Sub topic."""
        return self._mcp_call("fabric.publish", {
            "topic": topic,
            "data": data,
        })

    # ── Convenience Methods ───────────────────────────────────────────────────

    def ping(self) -> bool:
        """Quick connectivity check. Returns True if server is reachable."""
        try:
            self.health()
            return True
        except FabricError:
            return False

    def wait_for_server(self, timeout: float = 30.0, interval: float = 1.0) -> bool:
        """Block until the server becomes available."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.ping():
                return True
            time.sleep(interval)
        return False


# =============================================================================
# CLI entry point for quick testing
# =============================================================================

def main():
    """Quick CLI for testing connectivity."""
    import argparse

    parser = argparse.ArgumentParser(description="Fabric A2A SDK CLI")
    parser.add_argument("--url", default="http://localhost:8000", help="Fabric server URL")
    parser.add_argument("--key", default="", help="API key / master secret")
    parser.add_argument("command", choices=["health", "agents", "tools", "topics", "ping"],
                        help="Command to run")

    args = parser.parse_args()

    client = FabricClient(base_url=args.url, api_key=args.key)

    if args.command == "ping":
        ok = client.ping()
        print(f"Server {'reachable' if ok else 'unreachable'}")
    elif args.command == "health":
        print(json.dumps(client.health(), indent=2))
    elif args.command == "agents":
        agents = client.list_agents()
        for a in agents:
            print(f"  {a.agent_id:20s}  {a.display_name:20s}  {a.status}")
    elif args.command == "tools":
        tools = client.list_tools()
        print(json.dumps(tools, indent=2))
    elif args.command == "topics":
        topics = client.list_topics()
        print(json.dumps(topics, indent=2))

    client.close()


if __name__ == "__main__":
    main()

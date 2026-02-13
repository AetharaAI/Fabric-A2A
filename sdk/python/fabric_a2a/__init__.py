"""
Fabric A2A SDK - Python Client for Fabric Agent-to-Agent Protocol

A production-ready SDK for interacting with Fabric MCP Server.

Basic Usage:
    >>> from fabric_a2a import FabricClient
    >>>
    >>> client = FabricClient("https://fabric.perceptor.us", token="your-token")
    >>>
    >>> # Call a built-in tool
    >>> result = client.tools.math.calculate("2 + 2")
    >>> print(result)  # 4.0
    >>>
    >>> # Call an agent
    >>> response = client.agents.call("percy", "reason", "Explain Python")
    >>> print(response.result)

Async Usage:
    >>> from fabric_a2a import AsyncFabricClient
    >>>
    >>> async with AsyncFabricClient("https://fabric.perceptor.us", token="your-token") as client:
    >>>     result = await client.tools.math.calculate("2 + 2")

Async Messaging:
    >>> from fabric_a2a import MessagingClient
    >>>
    >>> client = MessagingClient(agent_id="my-agent", redis_url="redis://localhost:6379")
    >>> await client.send_message("percy", "task", {"task": "Analyze this"})
    >>> messages = await client.receive_messages()
"""

__version__ = "0.1.0"
__author__ = "AetherAI"

# Core clients
from fabric_a2a.client import FabricClient, AsyncFabricClient

# Sub-clients
from fabric_a2a.tools import ToolClient
from fabric_a2a.agents import AgentClient
from fabric_a2a.messaging import (
    MessagingClient,
    AsyncMessagingClient,
    Message,
    MessagePriority,
)

# Exceptions
from fabric_a2a.exceptions import (
    FabricError,
    AuthenticationError,
    AgentNotFoundError,
    CapabilityNotFoundError,
    ToolNotFoundError,
    TimeoutError,
)

# Data models
from fabric_a2a.models import (
    CallResult,
    AgentInfo,
    ToolInfo,
    TraceContext,
    HealthStatus,
)

# Streaming
from fabric_a2a.streaming import (
    StreamEvent,
    StreamEventType,
    StreamingResult,
    stream_sse,
    WebSocketClient,
)

__all__ = [
    # Core clients
    "FabricClient",
    "AsyncFabricClient",
    # Sub-clients
    "AgentClient",
    "ToolClient",
    "MessagingClient",
    "AsyncMessagingClient",
    # Messaging
    "Message",
    "MessagePriority",
    # Exceptions
    "FabricError",
    "AuthenticationError",
    "AgentNotFoundError",
    "CapabilityNotFoundError",
    "ToolNotFoundError",
    "TimeoutError",
    # Models
    "CallResult",
    "AgentInfo",
    "ToolInfo",
    "TraceContext",
    "HealthStatus",
    # Streaming
    "StreamEvent",
    "StreamEventType",
    "StreamingResult",
    "stream_sse",
    "WebSocketClient",
]

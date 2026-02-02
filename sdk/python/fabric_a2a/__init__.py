"""
Fabric A2A SDK - Python Client for Fabric MCP Server

A production-ready SDK for interacting with Fabric Agent-to-Agent protocol.

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
    >>> print(response.answer)

Async Usage:
    >>> from fabric_a2a import AsyncFabricClient
    >>> 
    >>> async with AsyncFabricClient("https://fabric.perceptor.us", token="your-token") as client:
    >>>     result = await client.tools.math.calculate("2 + 2")
"""

__version__ = "0.1.0"
__author__ = "AetherAI"

# Core clients
from fabric_a2a.client import FabricClient, AsyncFabricClient

# Sub-clients
from fabric_a2a.tools import ToolClient
from fabric_a2a.agents import AgentClient

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

__all__ = [
    # Core clients
    "FabricClient",
    "AsyncFabricClient",
    # Sub-clients
    "AgentClient",
    "ToolClient",
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
]

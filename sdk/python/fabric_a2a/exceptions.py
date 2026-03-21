"""
Fabric A2A SDK - Exceptions
Custom exception classes for the Fabric SDK.
"""

from typing import Optional, Dict


class FabricError(Exception):
    """Base exception for all Fabric SDK errors"""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        trace_id: Optional[str] = None,
        details: Optional[Dict] = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code or "UNKNOWN_ERROR"
        self.trace_id = trace_id
        self.details = details or {}

    def __str__(self):
        parts = [f"[{self.code}] {self.message}"]
        if self.trace_id:
            parts.append(f"Trace ID: {self.trace_id}")
        return " | ".join(parts)


class AuthenticationError(FabricError):
    """Raised when authentication fails"""

    def __init__(
        self,
        message: str = "Authentication failed",
        trace_id: Optional[str] = None
    ):
        super().__init__(message, code="AUTH_ERROR", trace_id=trace_id)


class AgentNotFoundError(FabricError):
    """Raised when requested agent is not found"""

    def __init__(
        self,
        agent_id: str,
        trace_id: Optional[str] = None
    ):
        super().__init__(
            f"Agent not found: {agent_id}",
            code="AGENT_NOT_FOUND",
            trace_id=trace_id,
            details={"agent_id": agent_id}
        )
        self.agent_id = agent_id


class CapabilityNotFoundError(FabricError):
    """Raised when agent doesn't have requested capability"""

    def __init__(
        self,
        agent_id: str,
        capability: str,
        trace_id: Optional[str] = None
    ):
        super().__init__(
            f"Capability '{capability}' not found on agent '{agent_id}'",
            code="CAPABILITY_NOT_FOUND",
            trace_id=trace_id,
            details={"agent_id": agent_id, "capability": capability}
        )
        self.agent_id = agent_id
        self.capability = capability


class ToolNotFoundError(FabricError):
    """Raised when requested tool is not found"""

    def __init__(
        self,
        tool_id: str,
        trace_id: Optional[str] = None
    ):
        super().__init__(
            f"Tool not found: {tool_id}",
            code="TOOL_NOT_FOUND",
            trace_id=trace_id,
            details={"tool_id": tool_id}
        )
        self.tool_id = tool_id


class TimeoutError(FabricError):
    """Raised when a call times out"""

    def __init__(
        self,
        operation: str,
        timeout: float,
        trace_id: Optional[str] = None
    ):
        super().__init__(
            f"Operation '{operation}' timed out after {timeout}s",
            code="TIMEOUT",
            trace_id=trace_id,
            details={"operation": operation, "timeout": timeout}
        )
        self.operation = operation
        self.timeout = timeout


class ConnectionError(FabricError):
    """Raised when connection to Fabric server fails"""

    def __init__(
        self,
        url: str,
        message: Optional[str] = None,
        trace_id: Optional[str] = None
    ):
        super().__init__(
            message or f"Failed to connect to {url}",
            code="CONNECTION_ERROR",
            trace_id=trace_id,
            details={"url": url}
        )
        self.url = url


class ValidationError(FabricError):
    """Raised when request validation fails"""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        trace_id: Optional[str] = None
    ):
        super().__init__(
            message,
            code="VALIDATION_ERROR",
            trace_id=trace_id,
            details={"field": field} if field else {}
        )
        self.field = field


class RateLimitError(FabricError):
    """Raised when rate limit is exceeded"""

    def __init__(
        self,
        retry_after: Optional[int] = None,
        trace_id: Optional[str] = None
    ):
        msg = "Rate limit exceeded"
        if retry_after:
            msg += f". Retry after {retry_after} seconds."

        super().__init__(
            msg,
            code="RATE_LIMITED",
            trace_id=trace_id,
            details={"retry_after": retry_after}
        )
        self.retry_after = retry_after

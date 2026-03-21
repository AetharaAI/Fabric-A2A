"""
Fabric A2A SDK - Agent Client
Convenient interface for calling agents.
"""

from typing import TYPE_CHECKING, Optional, Dict, Any, List

if TYPE_CHECKING:
    from fabric_a2a.client import FabricClient, AsyncFabricClient

from fabric_a2a.models import AgentInfo, AgentCapability, CallResult
from fabric_a2a.exceptions import (
    FabricError,
    AgentNotFoundError,
    CapabilityNotFoundError,
)


class AgentClient:
    """
    Client for calling Fabric agents.

    Access via:
        >>> client = FabricClient(...)
        >>> client.agents.call("percy", "reason", "Explain Python")
        >>>
        >>> # List all agents
        >>> agents = client.agents.list()
        >>>
        >>> # Get agent info
        >>> percy = client.agents.get("percy")
    """

    def __init__(self, client: "FabricClient"):
        self._client = client

    def list(
        self,
        capability: Optional[str] = None,
        tag: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[AgentInfo]:
        """
        List available agents.

        Args:
            capability: Filter by capability
            tag: Filter by tag
            status: Filter by status (online, offline, degraded)

        Returns:
            List of AgentInfo objects
        """
        args = {}
        if capability:
            args["capability"] = capability
        if tag:
            args["tag"] = tag
        if status:
            args["status"] = status

        result = self._client._make_request("GET", "/mcp/list_agents", data=args)
        agents_data = result.get("agents", [])

        agents = []
        for agent_data in agents_data:
            caps_data = agent_data.get("capabilities", [])
            capabilities = [
                AgentCapability(
                    name=c.get("name", ""),
                    description=c.get("description"),
                    streaming=c.get("streaming", False),
                    modalities=c.get("modalities", ["text"]),
                    input_schema=c.get("input_schema"),
                    output_schema=c.get("output_schema"),
                    max_timeout_ms=c.get("max_timeout_ms", 60000),
                )
                for c in caps_data
            ]

            agents.append(
                AgentInfo(
                    agent_id=agent_data.get("agent_id", ""),
                    display_name=agent_data.get("display_name", ""),
                    version=agent_data.get("version", "1.0.0"),
                    description=agent_data.get("description"),
                    status=agent_data.get("status", "unknown"),
                    capabilities=capabilities,
                    tags=agent_data.get("tags", []),
                    trust_tier=agent_data.get("trust_tier", "org"),
                    endpoint=agent_data.get("endpoint", {}).get("uri")
                    if isinstance(agent_data.get("endpoint"), dict)
                    else None,
                )
            )

        return agents

    def get(self, agent_id: str) -> Optional[AgentInfo]:
        """
        Get detailed information about an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            AgentInfo or None if not found
        """
        try:
            result = self._client._make_request("GET", f"/mcp/agent/{agent_id}")
            agent_data = result.get("agent", result)

            if not agent_data:
                return None

            caps_data = agent_data.get("capabilities", [])
            capabilities = [
                AgentCapability(
                    name=c.get("name", ""),
                    description=c.get("description"),
                    streaming=c.get("streaming", False),
                    modalities=c.get("modalities", ["text"]),
                    input_schema=c.get("input_schema"),
                    output_schema=c.get("output_schema"),
                    max_timeout_ms=c.get("max_timeout_ms", 60000),
                )
                for c in caps_data
            ]

            return AgentInfo(
                agent_id=agent_data.get("agent_id", ""),
                display_name=agent_data.get("display_name", ""),
                version=agent_data.get("version", "1.0.0"),
                description=agent_data.get("description"),
                status=agent_data.get("status", "unknown"),
                capabilities=capabilities,
                tags=agent_data.get("tags", []),
                trust_tier=agent_data.get("trust_tier", "org"),
                endpoint=agent_data.get("endpoint", {}).get("uri")
                if isinstance(agent_data.get("endpoint"), dict)
                else None,
            )

        except (FabricError, KeyError, TypeError):
            return None

    def call(
        self,
        agent_id: str,
        capability: str,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        timeout_ms: int = 60000,
        stream: bool = False,
    ) -> CallResult:
        """
        Call an agent's capability.

        Args:
            agent_id: Agent identifier
            capability: Capability name
            task: Task description/prompt
            context: Additional context
            timeout_ms: Timeout in milliseconds
            stream: Whether to stream response

        Returns:
            CallResult with agent's response

        Raises:
            AgentNotFoundError: If agent doesn't exist
            CapabilityNotFoundError: If agent doesn't have the capability
            TimeoutError: If call times out
        """
        args = {
            "agent_id": agent_id,
            "capability": capability,
            "task": task,
            "timeout_ms": timeout_ms,
            "stream": stream,
        }

        if context:
            args["context"] = context

        result = self._client.call("fabric.call", args)

        if not result.ok and result.error:
            error_msg = result.error
            trace_id = (
                result.trace.trace_id
                if result.trace and result.trace.trace_id
                else None
            )
            if "not found" in error_msg.lower() or "unknown agent" in error_msg.lower():
                raise AgentNotFoundError(agent_id, trace_id or "")
            elif "capability" in error_msg.lower():
                raise CapabilityNotFoundError(agent_id, capability, trace_id or "")

        return result

    def call_simple(self, agent_id: str, capability: str, task: str, **kwargs) -> str:
        """
        Simple agent call that returns just the answer string.

        Args:
            agent_id: Agent identifier
            capability: Capability name
            task: Task description
            **kwargs: Additional arguments (context, timeout, etc.)

        Returns:
            Agent's answer as string

        Example:
            >>> answer = client.agents.call_simple("percy", "reason", "Explain Python")
            >>> print(answer)
        """
        result = self.call(agent_id, capability, task, **kwargs)

        if (
            result.result
            and isinstance(result.result, dict)
            and "answer" in result.result
        ):
            return result.result["answer"]
        elif result.result:
            return str(result.result)
        else:
            return ""

    def find_by_capability(self, capability: str) -> List[AgentInfo]:
        """
        Find all agents that have a specific capability.

        Args:
            capability: Capability name to search for

        Returns:
            List of agents with that capability
        """
        return self.list(capability=capability)

    def is_available(self, agent_id: str) -> bool:
        """
        Check if an agent is available (online).

        Args:
            agent_id: Agent identifier

        Returns:
            True if agent is online
        """
        agent = self.get(agent_id)
        return agent is not None and agent.status == "online"

    def get_capabilities(self, agent_id: str) -> List[str]:
        """
        Get list of capability names for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            List of capability names
        """
        agent = self.get(agent_id)
        if agent:
            return [c.name for c in agent.capabilities]
        return []


class AsyncAgentClient:
    """
    Async agent client for high-concurrency applications.

    Use with AsyncFabricClient.
    """

    def __init__(self, client: "AsyncFabricClient"):
        self._client = client

    async def list(
        self,
        capability: Optional[str] = None,
        tag: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[AgentInfo]:
        """List agents asynchronously"""
        args = {}
        if capability:
            args["capability"] = capability
        if tag:
            args["tag"] = tag
        if status:
            args["status"] = status

        result = await self._client._make_request("GET", "/mcp/list_agents", data=args)
        agents_data = result.get("agents", [])

        agents = []
        for agent_data in agents_data:
            caps_data = agent_data.get("capabilities", [])
            capabilities = [
                AgentCapability(
                    name=c.get("name", ""),
                    description=c.get("description"),
                    streaming=c.get("streaming", False),
                    modalities=c.get("modalities", ["text"]),
                )
                for c in caps_data
            ]

            agents.append(
                AgentInfo(
                    agent_id=agent_data.get("agent_id", ""),
                    display_name=agent_data.get("display_name", ""),
                    version=agent_data.get("version", "1.0.0"),
                    status=agent_data.get("status", "unknown"),
                    capabilities=capabilities,
                    tags=agent_data.get("tags", []),
                    trust_tier=agent_data.get("trust_tier", "org"),
                )
            )

        return agents

    async def get(self, agent_id: str) -> Optional[AgentInfo]:
        """Get agent info asynchronously"""
        try:
            result = await self._client._make_request("GET", f"/mcp/agent/{agent_id}")
            agent_data = result.get("agent", result)

            if not agent_data:
                return None

            caps_data = agent_data.get("capabilities", [])
            capabilities = [
                AgentCapability(
                    name=c.get("name", ""),
                    description=c.get("description"),
                    streaming=c.get("streaming", False),
                    modalities=c.get("modalities", ["text"]),
                )
                for c in caps_data
            ]

            return AgentInfo(
                agent_id=agent_data.get("agent_id", ""),
                display_name=agent_data.get("display_name", ""),
                version=agent_data.get("version", "1.0.0"),
                capabilities=capabilities,
                status=agent_data.get("status", "unknown"),
            )

        except (FabricError, KeyError, TypeError):
            return None

    async def call(
        self,
        agent_id: str,
        capability: str,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        timeout_ms: int = 60000,
    ) -> CallResult:
        """Call agent asynchronously"""
        args = {
            "agent_id": agent_id,
            "capability": capability,
            "task": task,
            "timeout_ms": timeout_ms,
            "stream": False,
        }

        if context:
            args["context"] = context

        result = await self._client.call("fabric.call", args)
        return result

    async def call_simple(
        self, agent_id: str, capability: str, task: str, **kwargs
    ) -> str:
        """Simple async agent call"""
        result = await self.call(agent_id, capability, task, **kwargs)

        if (
            result.result
            and isinstance(result.result, dict)
            and "answer" in result.result
        ):
            return result.result["answer"]
        elif result.result:
            return str(result.result)
        return ""

#!/usr/bin/env python3
"""
Fabric MCP Server - Agent-to-Agent Communication Gateway
Production-grade MCP server for agent communication using MCP as the interface.
"""

import asyncio
import json
import logging
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# Import built-in tools
from tools.builtin_tools import execute_tool, list_builtin_tools, get_tool_info, BUILTIN_TOOLS
from tools.base import BaseTool

# Load tool plugins on startup
BaseTool.load_plugins("tools/plugins")

# --- add this right before logging.basicConfig(...) ---
_old_factory = logging.getLogRecordFactory()

def _record_factory(*args, **kwargs):
    record = _old_factory(*args, **kwargs)
    if not hasattr(record, "trace_id"):
        record.trace_id = "-"
    return record

logging.setLogRecordFactory(_record_factory)
# --- end add ---

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","level":"%(levelname)s","message":"%(message)s","trace_id":"%(trace_id)s"}',
    handlers=[logging.StreamHandler(sys.stderr)]
)

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================

class AuthMode(str, Enum):
    PSK = "psk"
    PASSPORT = "passport"
    MTLS = "mtls"
    NONE = "none"


class AgentStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class TransportType(str, Enum):
    HTTP = "http"
    WS = "ws"
    LOCAL = "local"
    STDIO = "stdio"


class TrustTier(str, Enum):
    LOCAL = "local"
    ORG = "org"
    PUBLIC = "public"


@dataclass
class TraceContext:
    """Distributed tracing context"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None

    @classmethod
    def create(cls, trace_id: Optional[str] = None, parent_span_id: Optional[str] = None):
        return cls(
            trace_id=trace_id or str(uuid.uuid4()),
            span_id=str(uuid.uuid4()),
            parent_span_id=parent_span_id
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id
        }


@dataclass
class AuthContext:
    """Authentication context"""
    mode: AuthMode
    principal_id: Optional[str] = None
    agent_passport_id: Optional[str] = None
    signature: Optional[str] = None
    key_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "principal_id": self.principal_id,
            "agent_passport_id": self.agent_passport_id,
            "signature": self.signature,
            "key_id": self.key_id
        }


@dataclass
class Capability:
    """Agent capability definition"""
    name: str
    description: str = ""
    modalities: List[str] = field(default_factory=lambda: ["text"])
    streaming: bool = False
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    max_timeout_ms: int = 60000


@dataclass
class AgentEndpoint:
    """Agent endpoint configuration"""
    transport: TransportType
    uri: str


@dataclass
class AgentManifest:
    """Complete agent registration manifest"""
    agent_id: str
    display_name: str
    version: str
    description: str = ""
    capabilities: List[Capability] = field(default_factory=list)
    endpoint: Optional[AgentEndpoint] = None
    tags: List[str] = field(default_factory=list)
    trust_tier: TrustTier = TrustTier.ORG
    status: AgentStatus = AgentStatus.UNKNOWN


@dataclass
class CanonicalEnvelope:
    """Internal routing envelope"""
    trace: TraceContext
    auth: AuthContext
    target: Dict[str, Any]
    input: Dict[str, Any]
    response: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace": self.trace.to_dict(),
            "auth": self.auth.to_dict(),
            "target": self.target,
            "input": self.input,
            "response": self.response
        }


class ErrorCode(str, Enum):
    AGENT_OFFLINE = "AGENT_OFFLINE"
    AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
    CAPABILITY_NOT_FOUND = "CAPABILITY_NOT_FOUND"
    AUTH_DENIED = "AUTH_DENIED"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    AUTH_INVALID = "AUTH_INVALID"
    TIMEOUT = "TIMEOUT"
    BAD_INPUT = "BAD_INPUT"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RATE_LIMITED = "RATE_LIMITED"


class FabricError(Exception):
    """Base exception for Fabric errors"""
    def __init__(self, code: ErrorCode, message: str, details: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)

    def to_dict(self, trace: TraceContext) -> Dict[str, Any]:
        return {
            "ok": False,
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details
            },
            "trace": trace.to_dict()
        }


# ============================================================================
# MCP Request/Response Models
# ============================================================================

class MCPToolCall(BaseModel):
    """MCP tool call request"""
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class MCPRequest(BaseModel):
    """MCP protocol request"""
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)


class MCPResponse(BaseModel):
    """MCP protocol response"""
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


# ============================================================================
# Runtime Adapter Interface
# ============================================================================

class RuntimeAdapter:
    """Base class for agent runtime adapters"""
    
    async def call(self, envelope: CanonicalEnvelope) -> Dict[str, Any]:
        """Execute a synchronous call"""
        raise NotImplementedError
    
    async def call_stream(self, envelope: CanonicalEnvelope) -> AsyncIterator[Dict[str, Any]]:
        """Execute a streaming call"""
        raise NotImplementedError
    
    async def health(self) -> AgentStatus:
        """Check agent health"""
        raise NotImplementedError
    
    async def describe(self) -> AgentManifest:
        """Get agent manifest"""
        raise NotImplementedError


class RuntimeMCP(RuntimeAdapter):
    """Adapter for agents that speak native MCP"""
    
    def __init__(self, agent_id: str, endpoint: AgentEndpoint, manifest: AgentManifest):
        self.agent_id = agent_id
        self.endpoint = endpoint
        self.manifest = manifest
    
    async def call(self, envelope: CanonicalEnvelope) -> Dict[str, Any]:
        """Call MCP agent synchronously"""
        # In production, this would make actual HTTP/WebSocket calls
        # For now, return a mock response
        logger.info(f"RuntimeMCP.call: {self.agent_id} / {envelope.target['capability']}")
        
        return {
            "ok": True,
            "trace": envelope.trace.to_dict(),
            "result": {
                "answer": f"Mock response from {self.agent_id}",
                "data": {},
                "artifacts": [],
                "citations": []
            }
        }
    
    async def call_stream(self, envelope: CanonicalEnvelope) -> AsyncIterator[Dict[str, Any]]:
        """Call MCP agent with streaming"""
        logger.info(f"RuntimeMCP.call_stream: {self.agent_id} / {envelope.target['capability']}")
        
        # Mock streaming response
        events = [
            {"event": "status", "data": {"status": "running", "message": "Starting task", "trace": envelope.trace.to_dict()}},
            {"event": "token", "data": {"text": "Processing ", "trace": envelope.trace.to_dict()}},
            {"event": "token", "data": {"text": "your ", "trace": envelope.trace.to_dict()}},
            {"event": "token", "data": {"text": "request...", "trace": envelope.trace.to_dict()}},
            {"event": "progress", "data": {"percent": 50, "message": "Halfway done", "trace": envelope.trace.to_dict()}},
            {"event": "token", "data": {"text": " Complete!", "trace": envelope.trace.to_dict()}},
            {"event": "final", "data": {
                "ok": True,
                "result": {"answer": f"Streamed response from {self.agent_id}", "data": {}},
                "trace": envelope.trace.to_dict()
            }}
        ]
        
        for event in events:
            await asyncio.sleep(0.1)  # Simulate processing time
            yield event
    
    async def health(self) -> AgentStatus:
        """Check agent health"""
        # In production, ping the actual endpoint
        return AgentStatus.ONLINE
    
    async def describe(self) -> AgentManifest:
        """Get agent manifest"""
        return self.manifest


class RuntimeAgentZero(RuntimeAdapter):
    """Adapter for Agent Zero RFC/FastA2A protocol"""
    
    def __init__(self, agent_id: str, endpoint: AgentEndpoint, manifest: AgentManifest):
        self.agent_id = agent_id
        self.endpoint = endpoint
        self.manifest = manifest
    
    async def call(self, envelope: CanonicalEnvelope) -> Dict[str, Any]:
        """Translate envelope to Agent Zero format and call"""
        logger.info(f"RuntimeAgentZero.call: {self.agent_id} / {envelope.target['capability']}")
        
        # Mock response
        return {
            "ok": True,
            "trace": envelope.trace.to_dict(),
            "result": {
                "answer": f"Agent Zero response from {self.agent_id}",
                "data": {}
            }
        }
    
    async def call_stream(self, envelope: CanonicalEnvelope) -> AsyncIterator[Dict[str, Any]]:
        """Streaming call via Agent Zero"""
        logger.info(f"RuntimeAgentZero.call_stream: {self.agent_id}")
        
        yield {"event": "status", "data": {"status": "running", "trace": envelope.trace.to_dict()}}
        yield {"event": "final", "data": {
            "ok": True,
            "result": {"answer": "Agent Zero streamed response"},
            "trace": envelope.trace.to_dict()
        }}
    
    async def health(self) -> AgentStatus:
        return AgentStatus.ONLINE
    
    async def describe(self) -> AgentManifest:
        return self.manifest


# ============================================================================
# Agent Registry
# ============================================================================

class AgentRegistry:
    """Agent registration and discovery"""
    
    def __init__(self):
        self.agents: Dict[str, AgentManifest] = {}
        self.adapters: Dict[str, RuntimeAdapter] = {}
    
    def register(self, manifest: AgentManifest, adapter: RuntimeAdapter):
        """Register an agent"""
        self.agents[manifest.agent_id] = manifest
        self.adapters[manifest.agent_id] = adapter
        logger.info(f"Registered agent: {manifest.agent_id} ({manifest.display_name})")
    
    def get_agent(self, agent_id: str) -> Optional[AgentManifest]:
        """Get agent by ID"""
        return self.agents.get(agent_id)
    
    def get_adapter(self, agent_id: str) -> Optional[RuntimeAdapter]:
        """Get runtime adapter for agent"""
        return self.adapters.get(agent_id)
    
    def list_agents(self, capability: Optional[str] = None, tag: Optional[str] = None, 
                   status: Optional[AgentStatus] = None) -> List[AgentManifest]:
        """List agents with optional filters"""
        agents = list(self.agents.values())
        
        if capability:
            agents = [a for a in agents if any(c.name == capability for c in a.capabilities)]
        
        if tag:
            agents = [a for a in agents if tag in a.tags]
        
        if status:
            agents = [a for a in agents if a.status == status]
        
        return agents
    
    def find_by_capability(self, capability: str) -> List[AgentManifest]:
        """Find all agents with a specific capability"""
        return [a for a in self.agents.values() 
                if any(c.name == capability for c in a.capabilities)]
    
    async def update_health_status(self):
        """Update health status for all agents"""
        for agent_id, adapter in self.adapters.items():
            try:
                status = await adapter.health()
                if agent_id in self.agents:
                    self.agents[agent_id].status = status
            except Exception as e:
                logger.error(f"Health check failed for {agent_id}: {e}")
                if agent_id in self.agents:
                    self.agents[agent_id].status = AgentStatus.OFFLINE


# ============================================================================
# Authentication
# ============================================================================

class AuthService:
    """Authentication and authorization service"""
    
    def __init__(self, psk: Optional[str] = None):
        self.psk = psk or "dev-shared-secret"  # Default for development
    
    def verify_psk(self, token: Optional[str]) -> AuthContext:
        """Verify pre-shared key"""
        if not token:
            raise FabricError(ErrorCode.AUTH_DENIED, "No authentication token provided")
        
        if token != self.psk:
            raise FabricError(ErrorCode.AUTH_INVALID, "Invalid authentication token")
        
        return AuthContext(
            mode=AuthMode.PSK,
            principal_id="psk-client"
        )
    
    def verify_passport(self, passport: Dict[str, Any]) -> AuthContext:
        """Verify agent passport (future implementation)"""
        # TODO: Implement Ed25519 signature verification
        # TODO: Check expiry
        # TODO: Validate delegation scope
        
        return AuthContext(
            mode=AuthMode.PASSPORT,
            principal_id=passport.get("principal_id"),
            agent_passport_id=passport.get("agent_passport_id"),
            signature=passport.get("signature"),
            key_id=passport.get("key_id")
        )


# ============================================================================
# Fabric MCP Server
# ============================================================================

class FabricServer:
    """Main Fabric MCP server"""
    
    def __init__(self, registry: AgentRegistry, auth_service: AuthService):
        self.registry = registry
        self.auth_service = auth_service
        self.start_time = time.time()
        self.version = "af-mcp-0.1"
    
    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any], 
                               auth_token: Optional[str] = None) -> Dict[str, Any]:
        """Handle MCP tool call"""
        trace = TraceContext.create(
            trace_id=arguments.get("trace", {}).get("trace_id"),
            parent_span_id=arguments.get("trace", {}).get("parent_span_id")
        )
        
        try:
            # Authenticate
            auth_ctx = self.auth_service.verify_psk(auth_token)
            
            # Route to appropriate handler
            if tool_name == "fabric.agent.list":
                return await self._handle_agent_list(arguments, trace, auth_ctx)
            elif tool_name == "fabric.agent.describe":
                return await self._handle_agent_describe(arguments, trace, auth_ctx)
            elif tool_name == "fabric.call":
                return await self._handle_call(arguments, trace, auth_ctx)
            elif tool_name == "fabric.route.preview":
                return await self._handle_route_preview(arguments, trace, auth_ctx)
            elif tool_name == "fabric.health":
                return await self._handle_health(arguments, trace, auth_ctx)
            elif tool_name == "fabric.tool.list":
                return await self._handle_tool_list(arguments, trace, auth_ctx)
            elif tool_name == "fabric.tool.call":
                return await self._handle_tool_call(arguments, trace, auth_ctx)
            elif tool_name == "fabric.tool.describe":
                return await self._handle_tool_describe(arguments, trace, auth_ctx)
            elif tool_name.startswith("fabric.tool.") and tool_name not in ["fabric.tool.list", "fabric.tool.call", "fabric.tool.describe"]:
                # Handle direct tool calls like fabric.tool.io.read_file
                return await self._handle_builtin_tool_direct(tool_name, arguments, trace, auth_ctx)
            else:
                raise FabricError(ErrorCode.BAD_INPUT, f"Unknown tool: {tool_name}")
        
        except FabricError as e:
            logger.error(f"FabricError: {e.code.value} - {e.message}", extra={"mcp_trace_id": trace.trace_id})
            return e.to_dict(trace)
        except Exception as e:
            logger.exception(f"Unexpected error: {e}", extra={"mcp_trace_id": trace.trace_id})
            return FabricError(ErrorCode.INTERNAL_ERROR, str(e)).to_dict(trace)
    
    async def _handle_agent_list(self, args: Dict[str, Any], trace: TraceContext, 
                                 auth: AuthContext) -> Dict[str, Any]:
        """Handle fabric.agent.list"""
        filter_args = args.get("filter", {})
        agents = self.registry.list_agents(
            capability=filter_args.get("capability"),
            tag=filter_args.get("tag"),
            status=AgentStatus(filter_args["status"]) if filter_args.get("status") else None
        )
        
        return {
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "display_name": a.display_name,
                    "version": a.version,
                    "status": a.status.value,
                    "endpoint": {
                        "transport": a.endpoint.transport.value,
                        "uri": a.endpoint.uri
                    } if a.endpoint else None,
                    "capabilities": [
                        {
                            "name": c.name,
                            "modalities": c.modalities,
                            "streaming": c.streaming
                        } for c in a.capabilities
                    ],
                    "tags": a.tags,
                    "trust_tier": a.trust_tier.value
                } for a in agents
            ]
        }
    
    async def _handle_agent_describe(self, args: Dict[str, Any], trace: TraceContext,
                                     auth: AuthContext) -> Dict[str, Any]:
        """Handle fabric.agent.describe"""
        agent_id = args.get("agent_id")
        if not agent_id:
            raise FabricError(ErrorCode.BAD_INPUT, "agent_id is required")
        
        agent = self.registry.get_agent(agent_id)
        if not agent:
            raise FabricError(ErrorCode.AGENT_NOT_FOUND, f"Agent not found: {agent_id}")
        
        return {
            "agent": {
                "agent_id": agent.agent_id,
                "display_name": agent.display_name,
                "version": agent.version,
                "description": agent.description,
                "capabilities": [
                    {
                        "name": c.name,
                        "description": c.description,
                        "input_schema": c.input_schema,
                        "output_schema": c.output_schema,
                        "streaming": c.streaming,
                        "max_timeout_ms": c.max_timeout_ms,
                        "modalities": c.modalities
                    } for c in agent.capabilities
                ],
                "endpoint": {
                    "transport": agent.endpoint.transport.value,
                    "uri": agent.endpoint.uri
                } if agent.endpoint else None,
                "tags": agent.tags,
                "trust_tier": agent.trust_tier.value
            }
        }
    
    async def _handle_call(self, args: Dict[str, Any], trace: TraceContext,
                          auth: AuthContext) -> Dict[str, Any]:
        """Handle fabric.call (non-streaming path)"""
        agent_id = args.get("agent_id")
        capability = args.get("capability")
        task = args.get("task")
        
        if not all([agent_id, capability, task]):
            raise FabricError(ErrorCode.BAD_INPUT, "agent_id, capability, and task are required")
        
        # Get agent and adapter
        agent = self.registry.get_agent(agent_id)
        if not agent:
            raise FabricError(ErrorCode.AGENT_NOT_FOUND, f"Agent not found: {agent_id}")
        
        if agent.status == AgentStatus.OFFLINE:
            raise FabricError(ErrorCode.AGENT_OFFLINE, f"Agent is offline: {agent_id}")
        
        # Verify capability
        cap = next((c for c in agent.capabilities if c.name == capability), None)
        if not cap:
            raise FabricError(ErrorCode.CAPABILITY_NOT_FOUND, 
                            f"Capability not found: {capability} on agent {agent_id}")
        
        adapter = self.registry.get_adapter(agent_id)
        if not adapter:
            raise FabricError(ErrorCode.INTERNAL_ERROR, f"No adapter for agent: {agent_id}")
        
        # Build envelope
        envelope = CanonicalEnvelope(
            trace=trace,
            auth=auth,
            target={
                "agent_id": agent_id,
                "capability": capability,
                "timeout_ms": args.get("timeout_ms", 60000)
            },
            input={
                "task": task,
                "context": args.get("context", {}),
                "attachments": []
            },
            response={
                "stream": args.get("stream", False),
                "format": "text"
            }
        )
        
        # Execute call
        logger.info(f"Executing call: {agent_id}.{capability}", extra={"mcp_trace_id": trace.trace_id})
        result = await adapter.call(envelope)
        return result
    
    async def _handle_call_stream(self, args: Dict[str, Any], trace: TraceContext,
                                  auth: AuthContext) -> AsyncIterator[str]:
        """Handle fabric.call (streaming path)"""
        agent_id = args.get("agent_id")
        capability = args.get("capability")
        
        agent = self.registry.get_agent(agent_id)
        if not agent:
            raise FabricError(ErrorCode.AGENT_NOT_FOUND, f"Agent not found: {agent_id}")
        
        adapter = self.registry.get_adapter(agent_id)
        if not adapter:
            raise FabricError(ErrorCode.INTERNAL_ERROR, f"No adapter for agent: {agent_id}")
        
        envelope = CanonicalEnvelope(
            trace=trace,
            auth=auth,
            target={
                "agent_id": agent_id,
                "capability": capability,
                "timeout_ms": args.get("timeout_ms", 60000)
            },
            input={
                "task": args.get("task", ""),
                "context": args.get("context", {}),
                "attachments": []
            },
            response={
                "stream": True,
                "format": "text"
            }
        )
        
        # Stream events
        async for event in adapter.call_stream(envelope):
            yield f"data: {json.dumps(event)}\n\n"
    
    async def _handle_route_preview(self, args: Dict[str, Any], trace: TraceContext,
                                   auth: AuthContext) -> Dict[str, Any]:
        """Handle fabric.route.preview"""
        agent_id = args.get("agent_id")
        capability = args.get("capability")
        
        if not all([agent_id, capability]):
            raise FabricError(ErrorCode.BAD_INPUT, "agent_id and capability are required")
        
        agent = self.registry.get_agent(agent_id)
        if not agent:
            raise FabricError(ErrorCode.AGENT_NOT_FOUND, f"Agent not found: {agent_id}")
        
        # Find fallbacks
        fallbacks = []
        other_agents = self.registry.find_by_capability(capability)
        for other in other_agents:
            if other.agent_id != agent_id:
                fallbacks.append({
                    "agent_id": other.agent_id,
                    "reason": f"Same capability: {capability}",
                    "priority": 1
                })
        
        return {
            "selected_runtime": {
                "transport": agent.endpoint.transport.value if agent.endpoint else "unknown",
                "uri": agent.endpoint.uri if agent.endpoint else "unknown",
                "adapter": "RuntimeMCP"  # Simplified for now
            },
            "policy": {
                "allowed": True,
                "reason": "ok"
            },
            "fallbacks": fallbacks
        }
    
    async def _handle_health(self, args: Dict[str, Any], trace: TraceContext,
                            auth: AuthContext) -> Dict[str, Any]:
        """Handle fabric.health"""
        await self.registry.update_health_status()
        
        agents = self.registry.list_agents()
        online = sum(1 for a in agents if a.status == AgentStatus.ONLINE)
        offline = sum(1 for a in agents if a.status == AgentStatus.OFFLINE)
        degraded = sum(1 for a in agents if a.status == AgentStatus.DEGRADED)
        
        builtin_tools = list_builtin_tools()
        
        return {
            "ok": True,
            "registry": "ok",
            "runtimes": {
                "online": online,
                "offline": offline,
                "degraded": degraded
            },
            "tools": {
                "builtin_count": len(builtin_tools),
                "available": builtin_tools[:10] + ["..."] if len(builtin_tools) > 10 else builtin_tools
            },
            "version": self.version,
            "uptime_seconds": int(time.time() - self.start_time)
        }
    
    # ============================================================================
    # Built-in Tool Handlers
    # ============================================================================
    
    async def _handle_tool_list(self, args: Dict[str, Any], trace: TraceContext,
                               auth: AuthContext) -> Dict[str, Any]:
        """Handle fabric.tool.list - list all available tools"""
        filter_category = args.get("category")
        filter_provider = args.get("provider")  # 'builtin' or 'agent'
        
        tools = []
        
        # Add built-in tools
        if not filter_provider or filter_provider == "builtin":
            for tool_id in list_builtin_tools():
                category = tool_id.split('.')[0] if '.' in tool_id else 'general'
                if filter_category and category != filter_category:
                    continue
                    
                tools.append({
                    "tool_id": tool_id,
                    "provider": "builtin",
                    "category": category,
                    "available": True
                })
        
        # Add agent-as-tools
        if not filter_provider or filter_provider == "agent":
            agents = self.registry.list_agents()
            for agent in agents:
                for cap in agent.capabilities:
                    tools.append({
                        "tool_id": f"agent.{agent.agent_id}.{cap.name}",
                        "provider": "agent",
                        "category": f"agent:{agent.agent_id}",
                        "agent_id": agent.agent_id,
                        "capability": cap.name,
                        "streaming": cap.streaming
                    })
        
        return {
            "tools": tools,
            "count": len(tools)
        }
    
    async def _handle_tool_call(self, args: Dict[str, Any], trace: TraceContext,
                               auth: AuthContext) -> Dict[str, Any]:
        """Handle fabric.tool.call - execute a built-in tool"""
        tool_id = args.get("tool_id")
        capability = args.get("capability", "")
        parameters = args.get("parameters", {})
        
        if not tool_id:
            raise FabricError(ErrorCode.BAD_INPUT, "tool_id is required")
        
        # Check if it's a built-in tool (legacy dict or new registry)
        if tool_id in BUILTIN_TOOLS or BaseTool.get_tool_class(tool_id):
            logger.info(f"Executing built-in tool: {tool_id}.{capability}", extra={"mcp_trace_id": trace.trace_id})
            
            # Add trace context to parameters
            parameters['_trace'] = {
                "trace_id": trace.trace_id,
                "span_id": trace.span_id
            }
            
            result = await execute_tool(tool_id, capability, parameters)
            
            # Add trace to result
            if isinstance(result, dict):
                result["trace"] = trace.to_dict()
            
            return result
        
        # Check if it's an agent capability
        if tool_id.startswith("agent."):
            parts = tool_id.split(".")
            if len(parts) >= 3:
                agent_id = parts[1]
                cap_name = parts[2]
                
                # Delegate to fabric.call
                call_args = {
                    "agent_id": agent_id,
                    "capability": cap_name,
                    "task": parameters.get("task", ""),
                    "context": parameters.get("context", {}),
                    "stream": args.get("stream", False)
                }
                return await self._handle_call(call_args, trace, auth)
        
        raise FabricError(ErrorCode.BAD_INPUT, f"Unknown tool: {tool_id}")
    
    async def _handle_tool_describe(self, args: Dict[str, Any], trace: TraceContext,
                                   auth: AuthContext) -> Dict[str, Any]:
        """Handle fabric.tool.describe - get tool details"""
        tool_id = args.get("tool_id")
        
        if not tool_id:
            raise FabricError(ErrorCode.BAD_INPUT, "tool_id is required")
        
        # Check built-in tools
        tool_info = get_tool_info(tool_id)
        if tool_info:
            return {
                "tool": {
                    "tool_id": tool_id,
                    "provider": "builtin",
                    "info": tool_info
                }
            }
        
        # Check if it's an agent reference
        if tool_id.startswith("agent."):
            parts = tool_id.split(".")
            if len(parts) >= 2:
                agent_id = parts[1]
                agent = self.registry.get_agent(agent_id)
                if agent:
                    return {
                        "tool": {
                            "tool_id": tool_id,
                            "provider": "agent",
                            "agent_id": agent_id,
                            "agent_info": {
                                "display_name": agent.display_name,
                                "capabilities": [
                                    {"name": c.name, "description": c.description}
                                    for c in agent.capabilities
                                ]
                            }
                        }
                    }
        
        raise FabricError(ErrorCode.BAD_INPUT, f"Tool not found: {tool_id}")
    
    async def _handle_builtin_tool_direct(self, tool_name: str, args: Dict[str, Any], 
                                         trace: TraceContext, auth: AuthContext) -> Dict[str, Any]:
        """Handle direct tool calls like fabric.tool.io.read_file"""
        # Parse tool_name: fabric.tool.<category>.<action>
        # e.g., fabric.tool.io.read_file -> category='io', action='read_file'
        parts = tool_name.split(".")
        if len(parts) >= 4:
            category = parts[2]
            action = parts[3]
            tool_id = f"{category}.{action}"
            
            if tool_id in BUILTIN_TOOLS or BaseTool.get_tool_class(tool_id):
                # Determine capability from tool definition
                if tool_id in BUILTIN_TOOLS:
                    tool_class, method_name = BUILTIN_TOOLS[tool_id]
                else:
                    tool_class = BaseTool.get_tool_class(tool_id)
                    method_name = None
                
                # Map method name to capability name
                capability_map = {
                    "read": "read",
                    "write": "write",
                    "list": "list",
                    "search": "search",
                    "request": "request",
                    "fetch": "fetch",
                    "parse_url": "parse_url",
                    "brave_search": "search",
                    "eval": "eval",
                    "analyze": "analyze",
                    "match": "match",
                    "transform": "transform",
                    "compare": "compare",
                    "exec": "exec",
                    "get": "get",
                    "now": "now",
                    "csv_parse": "csv_parse",
                    "hash": "hash",
                    "base64_encode": "base64_encode",
                    "url_encode": "url_encode",
                    "markdown_process": "markdown_process"
                }
                
                if method_name:
                    capability = capability_map.get(method_name, method_name)
                else:
                    # New BaseTool system - get first capability from tool class
                    capability = next(iter(tool_class.CAPABILITIES.keys()), None)
                
                logger.info(f"Executing direct tool call: {tool_id}.{capability}", extra={"mcp_trace_id": trace.trace_id})
                
                result = await execute_tool(tool_id, capability, args)
                
                if isinstance(result, dict):
                    result["trace"] = trace.to_dict()
                
                return result
        
        raise FabricError(ErrorCode.BAD_INPUT, f"Unknown built-in tool: {tool_name}")


# ============================================================================
# FastAPI HTTP Transport
# ============================================================================

def create_http_app(fabric: FabricServer) -> FastAPI:
    """Create FastAPI application for HTTP transport"""
    app = FastAPI(title="Fabric MCP Server", version=fabric.version)
    
    @app.post("/mcp/call")
    async def mcp_call(request: Request):
        """MCP tool call endpoint"""
        body = await request.json()
        tool_name = body.get("name")
        arguments = body.get("arguments", {})
        auth_token = request.headers.get("Authorization", "").replace("Bearer ", "")
        
        # Check if streaming is requested
        if arguments.get("stream"):
            trace = TraceContext.create()
            try:
                auth_ctx = fabric.auth_service.verify_psk(auth_token)
                return StreamingResponse(
                    fabric._handle_call_stream(arguments, trace, auth_ctx),
                    media_type="text/event-stream"
                )
            except FabricError as e:
                return e.to_dict(trace)
        
        result = await fabric.handle_tool_call(tool_name, arguments, auth_token)
        return result
    
    @app.get("/health")
    async def health():
        """Simple health check"""
        return {"status": "ok", "version": fabric.version}
    
    return app


# ============================================================================
# STDIO Transport
# ============================================================================

async def stdio_server(fabric: FabricServer):
    """Run MCP server over stdio"""
    logger.info("Starting Fabric MCP server on stdio")
    
    async def read_stdin():
        loop = asyncio.get_event_loop()
        while True:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                break
            yield line.strip()
    
    async for line in read_stdin():
        if not line:
            continue
        
        try:
            request = json.loads(line)
            tool_name = request.get("name")
            arguments = request.get("arguments", {})
            
            result = await fabric.handle_tool_call(tool_name, arguments)
            print(json.dumps(result), flush=True)
        
        except Exception as e:
            logger.exception(f"Error processing request: {e}")
            error_response = {
                "ok": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e)
                }
            }
            print(json.dumps(error_response), flush=True)


# ============================================================================
# Main Entry Point
# ============================================================================

def load_registry_from_yaml(registry: AgentRegistry, yaml_path: str):
    """Load agents from YAML configuration"""
    import yaml
    
    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)
    
    for agent_config in config.get("agents", []):
        # Build capabilities
        capabilities = []
        for cap_config in agent_config.get("capabilities", []):
            capabilities.append(Capability(
                name=cap_config["name"],
                description=cap_config.get("description", ""),
                modalities=cap_config.get("modalities", ["text"]),
                streaming=cap_config.get("streaming", False),
                input_schema=cap_config.get("input_schema", {}),
                output_schema=cap_config.get("output_schema", {}),
                max_timeout_ms=cap_config.get("max_timeout_ms", 60000)
            ))
        
        # Build endpoint
        endpoint_config = agent_config.get("endpoint", {})
        endpoint = AgentEndpoint(
            transport=TransportType(endpoint_config.get("transport", "http")),
            uri=endpoint_config.get("uri", "")
        )
        
        # Build manifest
        manifest = AgentManifest(
            agent_id=agent_config["agent_id"],
            display_name=agent_config.get("display_name", agent_config["agent_id"]),
            version=agent_config.get("version", "1.0.0"),
            description=agent_config.get("description", ""),
            capabilities=capabilities,
            endpoint=endpoint,
            tags=agent_config.get("tags", []),
            trust_tier=TrustTier(agent_config.get("trust_tier", "org")),
            status=AgentStatus.ONLINE
        )
        
        # Create adapter based on runtime type
        runtime_type = agent_config.get("runtime", "mcp")
        if runtime_type == "mcp":
            adapter = RuntimeMCP(manifest.agent_id, endpoint, manifest)
        elif runtime_type == "agentzero":
            adapter = RuntimeAgentZero(manifest.agent_id, endpoint, manifest)
        else:
            adapter = RuntimeMCP(manifest.agent_id, endpoint, manifest)
        
        registry.register(manifest, adapter)


async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Fabric MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default="stdio",
                       help="Transport protocol")
    parser.add_argument("--port", type=int, default=8000,
                       help="HTTP port (only for http transport)")
    parser.add_argument("--config", default="agents.yaml",
                       help="Path to agents configuration YAML")
    parser.add_argument("--psk", help="Pre-shared key for authentication")
    
    args = parser.parse_args()
    
    # Initialize components
    registry = AgentRegistry()
    auth_service = AuthService(psk=args.psk)
    fabric = FabricServer(registry, auth_service)
    
    # Load agents from config
    try:
        load_registry_from_yaml(registry, args.config)
    except FileNotFoundError:
        logger.warning(f"Config file not found: {args.config}, starting with empty registry")
    
    # Start server
    if args.transport == "stdio":
        await stdio_server(fabric)
    else:
        import uvicorn
        app = create_http_app(fabric)
        config = uvicorn.Config(app, host="0.0.0.0", port=args.port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()


if __name__ == "__main__":
    asyncio.run(main())

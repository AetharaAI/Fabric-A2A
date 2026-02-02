"""
Fabric A2A SDK - Data Models
Pydantic models for type-safe interactions with Fabric API.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class TraceContext(BaseModel):
    """Distributed tracing context"""
    trace_id: str = Field(..., description="Global trace identifier")
    span_id: str = Field(..., description="Local span identifier")
    parent_span_id: Optional[str] = Field(None, description="Parent span identifier")
    
    def __str__(self):
        return f"Trace({self.trace_id[:8]}.../{self.span_id[:8]}...)"


class CallResult(BaseModel):
    """Result of a Fabric call"""
    ok: bool = Field(..., description="Whether the call succeeded")
    trace: TraceContext = Field(..., description="Tracing information")
    result: Optional[Dict[str, Any]] = Field(None, description="Response data")
    error: Optional[str] = Field(None, description="Error message if failed")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")
    
    @property
    def success(self) -> bool:
        """Check if call was successful"""
        return self.ok and self.error is None
    
    def raise_for_error(self):
        """Raise exception if call failed"""
        if not self.success:
            from fabric_a2a.exceptions import FabricError
            raise FabricError(
                message=self.error or "Unknown error",
                code=self.error_code or "UNKNOWN",
                trace_id=self.trace.trace_id if self.trace else None
            )


class AgentCapability(BaseModel):
    """Agent capability definition"""
    name: str
    description: Optional[str] = None
    streaming: bool = False
    modalities: List[str] = Field(default_factory=lambda: ["text"])
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    max_timeout_ms: int = 60000


class AgentInfo(BaseModel):
    """Agent information"""
    agent_id: str
    display_name: str
    version: str = "1.0.0"
    description: Optional[str] = None
    status: str = "unknown"  # online, offline, degraded
    capabilities: List[AgentCapability] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    trust_tier: str = "org"
    endpoint: Optional[str] = None
    
    def has_capability(self, name: str) -> bool:
        """Check if agent has a specific capability"""
        return any(c.name == name for c in self.capabilities)


class ToolInfo(BaseModel):
    """Tool information"""
    tool_id: str
    display_name: str
    description: Optional[str] = None
    provider: str = "builtin"  # builtin, agent, external
    category: str
    capabilities: List[Dict[str, Any]] = Field(default_factory=list)
    available: bool = True
    
    @property
    def full_name(self) -> str:
        """Get full tool name for calling"""
        return f"fabric.tool.{self.tool_id}"


class HealthStatus(BaseModel):
    """Server health status"""
    status: str  # healthy, degraded, unhealthy
    version: str
    timestamp: datetime
    checks: Optional[Dict[str, Any]] = None
    
    @property
    def is_healthy(self) -> bool:
        return self.status == "healthy"


class ServerStatus(BaseModel):
    """Complete server status for AI agents"""
    schema_version: str
    timestamp: datetime
    fabric_version: str
    services: Dict[str, Any]
    endpoints: Dict[str, str]
    
    @property
    def available_agents(self) -> List[AgentInfo]:
        """Get list of available agents"""
        agents = self.services.get("agents", {}).get("available", [])
        return [AgentInfo(**a) for a in agents]
    
    @property
    def available_tools(self) -> List[ToolInfo]:
        """Get list of available tools"""
        tools = self.services.get("tools", {}).get("available", [])
        return [ToolInfo(**t) for t in tools]


class CallOptions(BaseModel):
    """Options for agent/tool calls"""
    timeout_ms: int = Field(default=60000, ge=1000, le=300000)
    stream: bool = False
    context: Optional[Dict[str, Any]] = None
    
    class Config:
        extra = "allow"  # Allow additional fields for extensibility


class FileContent(BaseModel):
    """Result of file read operation"""
    content: str
    line_count: int
    truncated: bool
    path: str
    size: int


class HTTPResponse(BaseModel):
    """Result of HTTP request"""
    status_code: int
    headers: Dict[str, str]
    body: str
    elapsed_ms: int
    url: str
    
    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300
    
    def json(self) -> Any:
        """Parse response body as JSON"""
        import json
        return json.loads(self.body)


class CalculationResult(BaseModel):
    """Result of math calculation"""
    result: float
    expression: str
    type: str


class HashResult(BaseModel):
    """Result of hash operation"""
    hash: str
    algorithm: str
    bytes: int
"""
Fabric MCP Server - PostgreSQL Registry Backend
Implements the registry interface using PostgreSQL for production deployments.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from contextlib import contextmanager

from sqlalchemy import func, desc
from sqlalchemy.orm import Session, joinedload

from database.models import (
    get_db_session, Agent, Capability, Tool, ToolCapability,
    HealthCheck, AgentMetrics, CallLog, AgentStatus, TrustTier
)
from server import AgentManifest, AgentEndpoint, Capability as CapabilityModel, AgentRegistry

logger = logging.getLogger(__name__)


class PostgresRegistry(AgentRegistry):
    """
    PostgreSQL-backed agent and tool registry.
    
    This replaces the in-memory YAML registry for production use,
    enabling dynamic registration, persistence, and horizontal scaling.
    """
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.SessionLocal = self._get_session_factory()
        logger.info("PostgreSQL registry initialized")
    
    def _get_session_factory(self):
        from database.models import get_session_factory
        return get_session_factory(self.database_url)
    
    @contextmanager
    def _get_session(self):
        """Get a database session with automatic cleanup"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    # ========================================================================
    # Agent Operations
    # ========================================================================
    
    def register(self, manifest: AgentManifest, adapter=None) -> None:
        """Register or update an agent"""
        with self._get_session() as session:
            # Check if agent exists
            db_agent = session.query(Agent).filter(Agent.agent_id == manifest.agent_id).first()
            
            if db_agent:
                # Update existing
                db_agent.display_name = manifest.display_name
                db_agent.version = manifest.version
                db_agent.description = manifest.description
                db_agent.runtime = manifest.runtime if hasattr(manifest, 'runtime') else 'mcp'
                db_agent.transport = manifest.endpoint.transport.value if manifest.endpoint else 'http'
                db_agent.endpoint_uri = manifest.endpoint.uri if manifest.endpoint else ''
                db_agent.tags = manifest.tags
                db_agent.trust_tier = TrustTier(manifest.trust_tier.value) if hasattr(manifest.trust_tier, 'value') else TrustTier.ORG
                db_agent.updated_at = datetime.utcnow()
                db_agent.status = AgentStatus.ONLINE
                db_agent.last_seen_at = datetime.utcnow()
                
                # Update capabilities
                session.query(Capability).filter(Capability.agent_id == db_agent.id).delete()
            else:
                # Create new
                db_agent = Agent(
                    agent_id=manifest.agent_id,
                    display_name=manifest.display_name,
                    version=manifest.version,
                    description=manifest.description,
                    runtime=getattr(manifest, 'runtime', 'mcp'),
                    transport=manifest.endpoint.transport.value if manifest.endpoint else 'http',
                    endpoint_uri=manifest.endpoint.uri if manifest.endpoint else '',
                    tags=manifest.tags,
                    trust_tier=TrustTier(manifest.trust_tier.value) if hasattr(manifest.trust_tier, 'value') else TrustTier.ORG,
                    status=AgentStatus.ONLINE,
                    last_seen_at=datetime.utcnow()
                )
                session.add(db_agent)
                session.flush()  # Get the ID
            
            # Add capabilities
            for cap in manifest.capabilities:
                db_cap = Capability(
                    agent_id=db_agent.id,
                    name=cap.name,
                    description=cap.description,
                    streaming=cap.streaming,
                    modalities=cap.modalities,
                    input_schema=cap.input_schema,
                    output_schema=cap.output_schema,
                    max_timeout_ms=cap.max_timeout_ms
                )
                session.add(db_cap)
            
            logger.info(f"Registered agent: {manifest.agent_id}")
    
    def get_agent(self, agent_id: str) -> Optional[AgentManifest]:
        """Get agent by ID"""
        with self._get_session() as session:
            db_agent = session.query(Agent).options(
                joinedload(Agent.capabilities)
            ).filter(Agent.agent_id == agent_id).first()
            
            if not db_agent:
                return None
            
            return self._db_agent_to_manifest(db_agent)
    
    def list_agents(self, capability: Optional[str] = None, 
                   tag: Optional[str] = None,
                   status: Optional[AgentStatus] = None) -> List[AgentManifest]:
        """List agents with optional filters"""
        with self._get_session() as session:
            query = session.query(Agent).options(joinedload(Agent.capabilities))
            
            if tag:
                query = query.filter(Agent.tags.contains([tag]))
            
            if status:
                query = query.filter(Agent.status == status)
            
            db_agents = query.all()
            
            # Filter by capability in Python (could be optimized with proper SQL)
            if capability:
                db_agents = [
                    a for a in db_agents 
                    if any(c.name == capability for c in a.capabilities)
                ]
            
            return [self._db_agent_to_manifest(a) for a in db_agents]
    
    def find_by_capability(self, capability: str) -> List[AgentManifest]:
        """Find all agents with a specific capability"""
        return self.list_agents(capability=capability)
    
    def get_adapter(self, agent_id: str):
        """Get runtime adapter for agent (delegated to parent)"""
        # Adapters are still created dynamically based on runtime type
        agent = self.get_agent(agent_id)
        if not agent:
            return None
        
        # Import here to avoid circular dependency
        from server import RuntimeMCP, RuntimeAgentZero
        
        endpoint = agent.endpoint
        runtime_type = getattr(agent, 'runtime', 'mcp')
        
        if runtime_type == 'agentzero':
            return RuntimeAgentZero(agent_id, endpoint, agent)
        else:
            return RuntimeMCP(agent_id, endpoint, agent)
    
    def unregister(self, agent_id: str) -> bool:
        """Unregister an agent"""
        with self._get_session() as session:
            result = session.query(Agent).filter(Agent.agent_id == agent_id).delete()
            return result > 0
    
    # ========================================================================
    # Tool Operations
    # ========================================================================
    
    def register_tool(self, tool_config: Dict[str, Any]) -> None:
        """Register a built-in tool"""
        with self._get_session() as session:
            db_tool = session.query(Tool).filter(Tool.tool_id == tool_config['tool_id']).first()
            
            if db_tool:
                # Update
                db_tool.display_name = tool_config.get('display_name', db_tool.display_name)
                db_tool.description = tool_config.get('description', db_tool.description)
                db_tool.category = tool_config.get('category', db_tool.category)
                db_tool.config = tool_config.get('config', db_tool.config)
                db_tool.updated_at = datetime.utcnow()
                
                # Update capabilities
                session.query(ToolCapability).filter(ToolCapability.tool_id == db_tool.id).delete()
            else:
                # Create
                db_tool = Tool(
                    tool_id=tool_config['tool_id'],
                    display_name=tool_config.get('display_name', tool_config['tool_id']),
                    description=tool_config.get('description', ''),
                    provider=tool_config.get('provider', 'builtin'),
                    category=tool_config.get('category', 'general'),
                    runtime=tool_config.get('runtime', 'builtin'),
                    trust_tier=TrustTier(tool_config.get('trust_tier', 'org')),
                    config=tool_config.get('config', {}),
                    enabled=tool_config.get('enabled', True)
                )
                session.add(db_tool)
                session.flush()
            
            # Add capabilities
            for cap in tool_config.get('capabilities', []):
                db_cap = ToolCapability(
                    tool_id=db_tool.id,
                    name=cap['name'],
                    description=cap.get('description', ''),
                    streaming=cap.get('streaming', False),
                    modalities=cap.get('modalities', ['text']),
                    input_schema=cap.get('input_schema', {}),
                    output_schema=cap.get('output_schema', {}),
                    max_timeout_ms=cap.get('max_timeout_ms', 60000)
                )
                session.add(db_cap)
    
    def get_tool(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """Get tool configuration"""
        with self._get_session() as session:
            db_tool = session.query(Tool).options(
                joinedload(Tool.capabilities)
            ).filter(Tool.tool_id == tool_id).first()
            
            if not db_tool:
                return None
            
            return self._db_tool_to_dict(db_tool)
    
    def list_tools(self, category: Optional[str] = None, 
                  provider: Optional[str] = None,
                  enabled_only: bool = True) -> List[Dict[str, Any]]:
        """List all tools with optional filters"""
        with self._get_session() as session:
            query = session.query(Tool).options(joinedload(Tool.capabilities))
            
            if category:
                query = query.filter(Tool.category == category)
            
            if provider:
                query = query.filter(Tool.provider == provider)
            
            if enabled_only:
                query = query.filter(Tool.enabled == True)
            
            db_tools = query.all()
            return [self._db_tool_to_dict(t) for t in db_tools]
    
    # ========================================================================
    # Health Operations
    # ========================================================================
    
    async def update_health_status(self) -> None:
        """Update health status for all agents"""
        with self._get_session() as session:
            agents = session.query(Agent).all()
            
            for agent in agents:
                try:
                    # Check if agent is stale (no health check in 5 minutes)
                    stale_threshold = datetime.utcnow() - timedelta(minutes=5)
                    
                    if agent.last_seen_at and agent.last_seen_at < stale_threshold:
                        agent.status = AgentStatus.OFFLINE
                    
                    # Log health check
                    health_check = HealthCheck(
                        agent_id=agent.id,
                        status=agent.status,
                        checked_at=datetime.utcnow()
                    )
                    session.add(health_check)
                    
                except Exception as e:
                    logger.error(f"Health check failed for {agent.agent_id}: {e}")
                    agent.status = AgentStatus.OFFLINE
    
    def update_agent_status(self, agent_id: str, status: AgentStatus, 
                           latency_ms: Optional[float] = None) -> None:
        """Update agent status"""
        with self._get_session() as session:
            agent = session.query(Agent).filter(Agent.agent_id == agent_id).first()
            if agent:
                agent.status = status
                agent.last_seen_at = datetime.utcnow()
                
                health_check = HealthCheck(
                    agent_id=agent.id,
                    status=status,
                    latency_ms=latency_ms,
                    checked_at=datetime.utcnow()
                )
                session.add(health_check)
    
    # ========================================================================
    # Observability - Call Logging
    # ========================================================================
    
    def log_call_start(self, trace_id: str, span_id: str, parent_span_id: Optional[str],
                      principal_id: Optional[str], auth_mode: Optional[str],
                      target_type: str, target_id: str, capability: Optional[str],
                      input_payload: Optional[Dict], streaming: bool = False) -> None:
        """Log the start of a call"""
        with self._get_session() as session:
            call_log = CallLog(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
                principal_id=principal_id,
                auth_mode=auth_mode,
                target_type=target_type,
                target_id=target_id,
                capability=capability,
                input_payload=input_payload,
                streaming=streaming,
                started_at=datetime.utcnow(),
                status="started"
            )
            session.add(call_log)
    
    def log_call_end(self, trace_id: str, span_id: str, 
                    output_payload: Optional[Dict],
                    error_code: Optional[str],
                    error_message: Optional[str],
                    duration_ms: float) -> None:
        """Log the end of a call"""
        with self._get_session() as session:
            call_log = session.query(CallLog).filter(
                CallLog.trace_id == trace_id,
                CallLog.span_id == span_id
            ).first()
            
            if call_log:
                call_log.output_payload = output_payload
                call_log.error_code = error_code
                call_log.error_message = error_message
                call_log.duration_ms = duration_ms
                call_log.completed_at = datetime.utcnow()
                call_log.status = "failed" if error_code else "completed"
    
    def get_call_logs(self, limit: int = 100, offset: int = 0,
                     target_type: Optional[str] = None,
                     target_id: Optional[str] = None,
                     status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get call logs for observability"""
        with self._get_session() as session:
            query = session.query(CallLog)
            
            if target_type:
                query = query.filter(CallLog.target_type == target_type)
            if target_id:
                query = query.filter(CallLog.target_id == target_id)
            if status:
                query = query.filter(CallLog.status == status)
            
            logs = query.order_by(desc(CallLog.started_at)).limit(limit).offset(offset).all()
            
            return [{
                "trace_id": log.trace_id,
                "span_id": log.span_id,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "capability": log.capability,
                "status": log.status,
                "duration_ms": log.duration_ms,
                "error_code": log.error_code,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "principal_id": log.principal_id
            } for log in logs]
    
    # ========================================================================
    # Statistics and Metrics
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        with self._get_session() as session:
            agent_stats = session.query(
                Agent.status,
                func.count(Agent.id)
            ).group_by(Agent.status).all()
            
            tool_count = session.query(Tool).filter(Tool.enabled == True).count()
            
            total_calls = session.query(CallLog).count()
            failed_calls = session.query(CallLog).filter(CallLog.status == "failed").count()
            
            # Recent calls (last hour)
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            recent_calls = session.query(CallLog).filter(CallLog.started_at >= hour_ago).count()
            
            return {
                "agents": {
                    "total": sum(count for _, count in agent_stats),
                    "by_status": {status.value: count for status, count in agent_stats}
                },
                "tools": {
                    "total": tool_count
                },
                "calls": {
                    "total": total_calls,
                    "failed": failed_calls,
                    "success_rate": (total_calls - failed_calls) / total_calls if total_calls > 0 else 1.0,
                    "last_hour": recent_calls
                }
            }
    
    # ========================================================================
    # Helper Methods
    # ========================================================================
    
    def _db_agent_to_manifest(self, db_agent: Agent) -> AgentManifest:
        """Convert database agent to AgentManifest"""
        from server import AgentManifest, AgentEndpoint, Capability as CapModel, TransportType, TrustTier, AgentStatus
        
        capabilities = [
            CapModel(
                name=c.name,
                description=c.description,
                streaming=c.streaming,
                modalities=c.modalities,
                input_schema=c.input_schema,
                output_schema=c.output_schema,
                max_timeout_ms=c.max_timeout_ms
            )
            for c in db_agent.capabilities
        ]
        
        manifest = AgentManifest(
            agent_id=db_agent.agent_id,
            display_name=db_agent.display_name,
            version=db_agent.version,
            description=db_agent.description,
            capabilities=capabilities,
            endpoint=AgentEndpoint(
                transport=TransportType(db_agent.transport),
                uri=db_agent.endpoint_uri
            ),
            tags=db_agent.tags or [],
            trust_tier=TrustTier(db_agent.trust_tier.value) if db_agent.trust_tier else TrustTier.ORG,
            status=AgentStatus(db_agent.status.value) if db_agent.status else AgentStatus.UNKNOWN
        )
        
        # Store runtime info
        manifest.runtime = db_agent.runtime
        
        return manifest
    
    def _db_tool_to_dict(self, db_tool: Tool) -> Dict[str, Any]:
        """Convert database tool to dictionary"""
        return {
            "tool_id": db_tool.tool_id,
            "display_name": db_tool.display_name,
            "description": db_tool.description,
            "provider": db_tool.provider,
            "category": db_tool.category,
            "trust_tier": db_tool.trust_tier.value if db_tool.trust_tier else "org",
            "enabled": db_tool.enabled,
            "capabilities": [
                {
                    "name": c.name,
                    "description": c.description,
                    "streaming": c.streaming,
                    "modalities": c.modalities
                }
                for c in db_tool.capabilities
            ]
        }

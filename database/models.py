"""
Fabric MCP Server - Database Models
SQLAlchemy models for PostgreSQL registry backend.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum as PyEnum

from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean, 
    DateTime, Text, ForeignKey, JSON, Enum, Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid

Base = declarative_base()


class AgentStatus(str, PyEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class TrustTier(str, PyEnum):
    LOCAL = "local"
    ORG = "org"
    PUBLIC = "public"


class Agent(Base):
    """Agent registration table"""
    __tablename__ = "agents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(String(255), unique=True, nullable=False, index=True)
    node_id = Column(String(255), nullable=True)
    delegate_id = Column(String(255), nullable=True)
    cog_id = Column(String(255), nullable=True)
    realm = Column(String(100), default="master")
    display_name = Column(String(255), nullable=False)
    version = Column(String(50), default="1.0.0")
    description = Column(Text, nullable=True)
    runtime = Column(String(50), default="mcp")
    
    # Endpoint configuration
    transport = Column(String(20), default="http")
    endpoint_uri = Column(String(500), nullable=False)
    
    # Status and metadata
    status = Column(Enum(AgentStatus), default=AgentStatus.UNKNOWN)
    trust_tier = Column(Enum(TrustTier), default=TrustTier.ORG)
    tags = Column(ARRAY(String), default=[])
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=True)
    
    # Relationships
    capabilities = relationship("Capability", back_populates="agent", cascade="all, delete-orphan")
    health_checks = relationship("HealthCheck", back_populates="agent", cascade="all, delete-orphan")
    metrics = relationship("AgentMetrics", back_populates="agent", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_agent_status', 'status'),
        Index('idx_agent_trust_tier', 'trust_tier'),
        Index('idx_agent_runtime', 'runtime'),
    )


class Capability(Base):
    """Agent capabilities table"""
    __tablename__ = "capabilities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    streaming = Column(Boolean, default=False)
    modalities = Column(ARRAY(String), default=["text"])
    input_schema = Column(JSON, default={})
    output_schema = Column(JSON, default={})
    max_timeout_ms = Column(Integer, default=60000)
    
    # Relationships
    agent = relationship("Agent", back_populates="capabilities")
    
    __table_args__ = (
        UniqueConstraint('agent_id', 'name', name='uq_agent_capability'),
        Index('idx_capability_name', 'name'),
    )


class Tool(Base):
    """Built-in tools registry"""
    __tablename__ = "tools"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tool_id = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    provider = Column(String(50), default="builtin")  # builtin, agent, external
    category = Column(String(50), nullable=False, index=True)
    runtime = Column(String(50), default="builtin")
    
    # Trust and access control
    trust_tier = Column(Enum(TrustTier), default=TrustTier.ORG)
    
    # Configuration
    config = Column(JSON, default={})
    
    # Status
    enabled = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    capabilities = relationship("ToolCapability", back_populates="tool", cascade="all, delete-orphan")
    metrics = relationship("ToolMetrics", back_populates="tool", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_tool_category', 'category'),
        Index('idx_tool_provider', 'provider'),
        Index('idx_tool_enabled', 'enabled'),
    )


class ToolCapability(Base):
    """Tool capabilities (for built-in tools)"""
    __tablename__ = "tool_capabilities"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tool_id = Column(UUID(as_uuid=True), ForeignKey("tools.id", ondelete="CASCADE"), nullable=False)
    
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    streaming = Column(Boolean, default=False)
    modalities = Column(ARRAY(String), default=["text"])
    input_schema = Column(JSON, default={})
    output_schema = Column(JSON, default={})
    max_timeout_ms = Column(Integer, default=60000)
    
    # Relationships
    tool = relationship("Tool", back_populates="capabilities")
    
    __table_args__ = (
        UniqueConstraint('tool_id', 'name', name='uq_tool_capability'),
    )


class HealthCheck(Base):
    """Agent health check history"""
    __tablename__ = "health_checks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    
    status = Column(Enum(AgentStatus), nullable=False)
    latency_ms = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    
    checked_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    agent = relationship("Agent", back_populates="health_checks")
    
    __table_args__ = (
        Index('idx_health_check_agent', 'agent_id', 'checked_at'),
        Index('idx_health_check_status', 'status', 'checked_at'),
    )


class AgentMetrics(Base):
    """Agent usage metrics"""
    __tablename__ = "agent_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    
    # Call statistics
    total_calls = Column(Integer, default=0)
    successful_calls = Column(Integer, default=0)
    failed_calls = Column(Integer, default=0)
    
    # Latency metrics (in milliseconds)
    avg_latency_ms = Column(Float, nullable=True)
    min_latency_ms = Column(Float, nullable=True)
    max_latency_ms = Column(Float, nullable=True)
    p95_latency_ms = Column(Float, nullable=True)
    p99_latency_ms = Column(Float, nullable=True)
    
    # Time window
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    granularity = Column(String(20), default="hour")  # minute, hour, day
    
    # Relationships
    agent = relationship("Agent", back_populates="metrics")
    
    __table_args__ = (
        Index('idx_agent_metrics_period', 'agent_id', 'period_start', 'period_end'),
        Index('idx_agent_metrics_granularity', 'granularity', 'period_start'),
    )


class ToolMetrics(Base):
    """Built-in tool usage metrics"""
    __tablename__ = "tool_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tool_id = Column(UUID(as_uuid=True), ForeignKey("tools.id", ondelete="CASCADE"), nullable=False)
    
    # Call statistics
    total_calls = Column(Integer, default=0)
    successful_calls = Column(Integer, default=0)
    failed_calls = Column(Integer, default=0)
    
    # Latency metrics
    avg_latency_ms = Column(Float, nullable=True)
    min_latency_ms = Column(Float, nullable=True)
    max_latency_ms = Column(Float, nullable=True)
    
    # Time window
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    granularity = Column(String(20), default="hour")
    
    # Relationships
    tool = relationship("Tool", back_populates="metrics")
    
    __table_args__ = (
        Index('idx_tool_metrics_period', 'tool_id', 'period_start', 'period_end'),
    )


class CallLog(Base):
    """Detailed call logs for observability"""
    __tablename__ = "call_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(String(36), nullable=False, index=True)
    span_id = Column(String(36), nullable=False)
    parent_span_id = Column(String(36), nullable=True)
    
    # Caller information
    principal_id = Column(String(255), nullable=True)
    auth_mode = Column(String(50), nullable=True)
    
    # Target information
    target_type = Column(String(50), nullable=False)  # agent, tool
    target_id = Column(String(255), nullable=False)
    capability = Column(String(100), nullable=True)
    
    # Call details
    input_payload = Column(JSON, nullable=True)
    output_payload = Column(JSON, nullable=True)
    error_code = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Float, nullable=True)
    
    # Status
    status = Column(String(20), default="started")  # started, completed, failed
    streaming = Column(Boolean, default=False)
    
    __table_args__ = (
        Index('idx_call_log_trace', 'trace_id', 'started_at'),
        Index('idx_call_log_target', 'target_type', 'target_id', 'started_at'),
        Index('idx_call_log_principal', 'principal_id', 'started_at'),
        Index('idx_call_log_status', 'status', 'started_at'),
    )


class RegistryMetadata(Base):
    """Registry metadata and configuration"""
    __tablename__ = "registry_metadata"
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(JSON, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Database initialization
def init_database(database_url: str) -> None:
    """Create all tables"""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)


def get_session_factory(database_url: str):
    """Get a session factory for the database"""
    engine = create_engine(database_url, pool_pre_ping=True)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session(database_url: str) -> Session:
    """Get a database session"""
    SessionLocal = get_session_factory(database_url)
    return SessionLocal()

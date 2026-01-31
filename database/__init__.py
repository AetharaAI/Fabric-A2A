"""
Fabric MCP Server - Database Module
PostgreSQL registry and database models.
"""

from database.models import (
    Base,
    Agent,
    Capability,
    Tool,
    ToolCapability,
    HealthCheck,
    AgentMetrics,
    ToolMetrics,
    CallLog,
    AgentStatus,
    TrustTier,
    init_database,
    get_db_session,
)

from database.postgres_registry import PostgresRegistry

__all__ = [
    'Base',
    'Agent',
    'Capability',
    'Tool',
    'ToolCapability',
    'HealthCheck',
    'AgentMetrics',
    'ToolMetrics',
    'CallLog',
    'AgentStatus',
    'TrustTier',
    'init_database',
    'get_db_session',
    'PostgresRegistry',
]
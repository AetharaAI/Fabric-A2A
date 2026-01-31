"""
Fabric MCP Server - Observability Module
Metrics, monitoring, and observability for both AI agents and humans.
"""

from observability.metrics import (
    FabricMetrics,
    StructuredLogger,
    get_metrics,
    get_logger,
    monitored,
)

from observability.dashboard import (
    router,
    get_dashboard_data,
)

__all__ = [
    'FabricMetrics',
    'StructuredLogger',
    'get_metrics',
    'get_logger',
    'monitored',
    'router',
    'get_dashboard_data',
]
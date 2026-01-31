"""
Fabric MCP Server - Observability and Metrics
Prometheus metrics and monitoring for both AI agents and humans.
"""

import time
import logging
from typing import Dict, Any, Optional, Callable
from functools import wraps
from contextlib import contextmanager

# Prometheus client
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.registry import CollectorRegistry

logger = logging.getLogger(__name__)


class FabricMetrics:
    """
    Centralized metrics collection for Fabric MCP Server.
    
    Provides both Prometheus metrics (machine-readable) and
    structured logging (human-readable) for complete observability.
    """
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        self.registry = registry or CollectorRegistry()
        
        # Server info
        self.info = Info('fabric_server', 'Fabric MCP Server information', registry=self.registry)
        
        # Call counters
        self.calls_total = Counter(
            'fabric_calls_total',
            'Total number of calls',
            ['target_type', 'target_id', 'capability', 'status'],
            registry=self.registry
        )
        
        # Call latency
        self.call_duration = Histogram(
            'fabric_call_duration_seconds',
            'Call duration in seconds',
            ['target_type', 'target_id', 'capability'],
            buckets=[.005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0, float('inf')],
            registry=self.registry
        )
        
        # Agent metrics
        self.agent_status = Gauge(
            'fabric_agent_status',
            'Agent status (1=online, 0=offline, 0.5=degraded)',
            ['agent_id'],
            registry=self.registry
        )
        
        self.agent_last_seen = Gauge(
            'fabric_agent_last_seen_timestamp',
            'Last time agent was seen',
            ['agent_id'],
            registry=self.registry
        )
        
        # Tool metrics
        self.tool_calls = Counter(
            'fabric_tool_calls_total',
            'Total tool calls',
            ['tool_id', 'capability', 'status'],
            registry=self.registry
        )
        
        self.tool_duration = Histogram(
            'fabric_tool_duration_seconds',
            'Tool execution duration',
            ['tool_id', 'capability'],
            registry=self.registry
        )
        
        # Registry metrics
        self.registry_agents = Gauge(
            'fabric_registry_agents',
            'Number of registered agents',
            ['status'],
            registry=self.registry
        )
        
        self.registry_tools = Gauge(
            'fabric_registry_tools',
            'Number of registered tools',
            ['category'],
            registry=self.registry
        )
        
        # Error tracking
        self.errors_total = Counter(
            'fabric_errors_total',
            'Total errors',
            ['error_code', 'target_type'],
            registry=self.registry
        )
        
        # Active connections/streams
        self.active_streams = Gauge(
            'fabric_active_streams',
            'Number of active streaming connections',
            registry=self.registry
        )
        
        # Authentication metrics
        self.auth_attempts = Counter(
            'fabric_auth_attempts_total',
            'Authentication attempts',
            ['auth_mode', 'status'],
            registry=self.registry
        )
        
        # Set server info
        self.info.info({'version': 'af-mcp-0.1', 'registry': 'postgres'})
    
    def record_call(self, target_type: str, target_id: str, capability: str,
                   duration: float, success: bool, error_code: Optional[str] = None):
        """Record a completed call"""
        status = "success" if success else "failure"
        
        self.calls_total.labels(
            target_type=target_type,
            target_id=target_id,
            capability=capability,
            status=status
        ).inc()
        
        self.call_duration.labels(
            target_type=target_type,
            target_id=target_id,
            capability=capability
        ).observe(duration)
        
        if error_code:
            self.errors_total.labels(
                error_code=error_code,
                target_type=target_type
            ).inc()
    
    def record_tool_call(self, tool_id: str, capability: str, duration: float, success: bool):
        """Record a built-in tool call"""
        status = "success" if success else "failure"
        
        self.tool_calls.labels(
            tool_id=tool_id,
            capability=capability,
            status=status
        ).inc()
        
        self.tool_duration.labels(
            tool_id=tool_id,
            capability=capability
        ).observe(duration)
    
    def update_agent_status(self, agent_id: str, status: str, last_seen: Optional[float] = None):
        """Update agent status metric"""
        status_value = {
            "online": 1.0,
            "offline": 0.0,
            "degraded": 0.5,
            "unknown": -1.0
        }.get(status, -1.0)
        
        self.agent_status.labels(agent_id=agent_id).set(status_value)
        
        if last_seen:
            self.agent_last_seen.labels(agent_id=agent_id).set(last_seen)
    
    def update_registry_stats(self, agents_by_status: Dict[str, int], tools_by_category: Dict[str, int]):
        """Update registry statistics"""
        for status, count in agents_by_status.items():
            self.registry_agents.labels(status=status).set(count)
        
        for category, count in tools_by_category.items():
            self.registry_tools.labels(category=category).set(count)
    
    def record_auth(self, auth_mode: str, success: bool):
        """Record authentication attempt"""
        status = "success" if success else "failure"
        self.auth_attempts.labels(auth_mode=auth_mode, status=status).inc()
    
    @contextmanager
    def measure_call(self, target_type: str, target_id: str, capability: str):
        """Context manager to measure call duration"""
        start = time.time()
        success = True
        
        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            duration = time.time() - start
            self.record_call(target_type, target_id, capability, duration, success)
    
    def get_prometheus_metrics(self) -> bytes:
        """Get Prometheus-formatted metrics"""
        return generate_latest(self.registry)
    
    def get_content_type(self) -> str:
        """Get Prometheus content type"""
        return CONTENT_TYPE_LATEST


class StructuredLogger:
    """
    Structured logging for human and machine readability.
    
    Produces JSON logs that can be:
    - Read by humans (formatted)
    - Parsed by AI agents (structured)
    - Ingested by log aggregation systems (ELK, Loki, etc.)
    """
    
    def __init__(self, name: str = "fabric"):
        self.logger = logging.getLogger(name)
    
    def _log(self, level: str, message: str, trace_id: Optional[str] = None,
            extra: Optional[Dict[str, Any]] = None):
        """Create structured log entry"""
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "level": level,
            "message": message,
            "trace_id": trace_id,
        }
        
        if extra:
            log_entry.update(extra)
        
        # Log as JSON for machine parsing
        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(json.dumps(log_entry))
        
        return log_entry
    
    def info(self, message: str, trace_id: Optional[str] = None, extra: Optional[Dict] = None):
        return self._log("INFO", message, trace_id, extra)
    
    def warning(self, message: str, trace_id: Optional[str] = None, extra: Optional[Dict] = None):
        return self._log("WARNING", message, trace_id, extra)
    
    def error(self, message: str, trace_id: Optional[str] = None, extra: Optional[Dict] = None):
        return self._log("ERROR", message, trace_id, extra)
    
    def debug(self, message: str, trace_id: Optional[str] = None, extra: Optional[Dict] = None):
        return self._log("DEBUG", message, trace_id, extra)
    
    def call_started(self, trace_id: str, span_id: str, target_type: str, 
                    target_id: str, capability: str, principal: Optional[str] = None):
        """Log call start"""
        return self.info(
            f"Call started: {target_type}.{target_id}.{capability}",
            trace_id=trace_id,
            extra={
                "span_id": span_id,
                "target_type": target_type,
                "target_id": target_id,
                "capability": capability,
                "principal": principal,
                "event": "call_started"
            }
        )
    
    def call_completed(self, trace_id: str, span_id: str, target_type: str,
                      target_id: str, capability: str, duration_ms: float,
                      status: str, error_code: Optional[str] = None):
        """Log call completion"""
        return self.info(
            f"Call completed: {target_type}.{target_id}.{capability} ({status})",
            trace_id=trace_id,
            extra={
                "span_id": span_id,
                "target_type": target_type,
                "target_id": target_id,
                "capability": capability,
                "duration_ms": duration_ms,
                "status": status,
                "error_code": error_code,
                "event": "call_completed"
            }
        )
    
    def agent_registered(self, agent_id: str, capabilities: list):
        """Log agent registration"""
        return self.info(
            f"Agent registered: {agent_id}",
            extra={
                "agent_id": agent_id,
                "capabilities": capabilities,
                "event": "agent_registered"
            }
        )
    
    def health_check(self, agent_id: str, status: str, latency_ms: Optional[float] = None):
        """Log health check"""
        return self.info(
            f"Health check: {agent_id} is {status}",
            extra={
                "agent_id": agent_id,
                "status": status,
                "latency_ms": latency_ms,
                "event": "health_check"
            }
        )


# Singleton instances
_metrics: Optional[FabricMetrics] = None
_logger: Optional[StructuredLogger] = None


def get_metrics() -> FabricMetrics:
    """Get or create metrics singleton"""
    global _metrics
    if _metrics is None:
        _metrics = FabricMetrics()
    return _metrics


def get_logger() -> StructuredLogger:
    """Get or create logger singleton"""
    global _logger
    if _logger is None:
        _logger = StructuredLogger()
    return _logger


def reset_metrics():
    """Reset metrics (useful for testing)"""
    global _metrics
    _metrics = None


# Decorator for automatic metrics collection
def monitored(target_type: str, target_id_arg: str = "agent_id", capability_arg: str = "capability"):
    """Decorator to automatically monitor function calls"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            target_id = kwargs.get(target_id_arg, "unknown")
            capability = kwargs.get(capability_arg, "unknown")
            
            metrics = get_metrics()
            start = time.time()
            success = True
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise e
            finally:
                duration = time.time() - start
                metrics.record_call(target_type, target_id, capability, duration, success)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            target_id = kwargs.get(target_id_arg, "unknown")
            capability = kwargs.get(capability_arg, "unknown")
            
            metrics = get_metrics()
            start = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise e
            finally:
                duration = time.time() - start
                metrics.record_call(target_type, target_id, capability, duration, success)
        
        # Return async wrapper if the function is async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


import json  # Add json import for StructuredLogger
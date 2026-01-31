"""
Fabric MCP Server - Monitoring Dashboard
Web-based dashboard for human-readable monitoring.
"""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


# HTML Template for the dashboard
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fabric MCP Server - Monitoring</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            line-height: 1.6;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        header { 
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            border: 1px solid #334155;
        }
        h1 { font-size: 2.5rem; margin-bottom: 10px; color: #60a5fa; }
        .subtitle { color: #94a3b8; font-size: 1.1rem; }
        .grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card { 
            background: #1e293b;
            padding: 24px;
            border-radius: 12px;
            border: 1px solid #334155;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        .card h2 { 
            font-size: 0.875rem; 
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #94a3b8;
            margin-bottom: 12px;
        }
        .metric { 
            font-size: 2.5rem; 
            font-weight: 700;
            color: #60a5fa;
        }
        .metric.success { color: #4ade80; }
        .metric.warning { color: #fbbf24; }
        .metric.error { color: #f87171; }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-online { background: #4ade80; box-shadow: 0 0 10px #4ade80; }
        .status-offline { background: #f87171; }
        .status-degraded { background: #fbbf24; }
        table { 
            width: 100%; 
            border-collapse: collapse;
            background: #1e293b;
            border-radius: 12px;
            overflow: hidden;
        }
        th, td { 
            padding: 16px;
            text-align: left;
            border-bottom: 1px solid #334155;
        }
        th { 
            background: #0f172a;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
            color: #94a3b8;
        }
        tr:hover { background: #252f47; }
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .badge-online { background: rgba(74, 222, 128, 0.2); color: #4ade80; }
        .badge-offline { background: rgba(248, 113, 113, 0.2); color: #f87171; }
        .badge-degraded { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }
        .refresh-btn {
            background: #3b82f6;
            color: white;
            border: none;
            padding: 10px 24px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1rem;
            margin-bottom: 20px;
        }
        .refresh-btn:hover { background: #2563eb; }
        .section-title {
            font-size: 1.5rem;
            margin: 30px 0 20px;
            color: #e2e8f0;
        }
        .endpoint-list {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .endpoint {
            background: #0f172a;
            padding: 8px 16px;
            border-radius: 6px;
            font-family: monospace;
            font-size: 0.875rem;
            border: 1px solid #334155;
        }
        @media (max-width: 768px) {
            .grid { grid-template-columns: 1fr; }
            h1 { font-size: 1.75rem; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔧 Fabric MCP Server</h1>
            <p class="subtitle">Universal Tool Server & Agent Gateway - Monitoring Dashboard</p>
        </header>
        
        <button class="refresh-btn" onclick="location.reload()">🔄 Refresh Dashboard</button>
        
        <div class="grid">
            <div class="card">
                <h2>Server Status</h2>
                <div class="metric success">● Online</div>
                <p style="margin-top: 10px; color: #94a3b8;">Version: {{ version }}</p>
                <p style="color: #94a3b8;">Uptime: {{ uptime }}</p>
            </div>
            
            <div class="card">
                <h2>Registered Agents</h2>
                <div class="metric">{{ total_agents }}</div>
                <p style="margin-top: 10px;">
                    <span class="badge badge-online">{{ online_agents }} Online</span>
                    <span class="badge badge-offline">{{ offline_agents }} Offline</span>
                </p>
            </div>
            
            <div class="card">
                <h2>Built-in Tools</h2>
                <div class="metric">{{ total_tools }}</div>
                <p style="margin-top: 10px; color: #94a3b8;">Across {{ tool_categories }} categories</p>
            </div>
            
            <div class="card">
                <h2>Total Calls (Last Hour)</h2>
                <div class="metric {{ 'success' if success_rate > 0.95 else 'warning' if success_rate > 0.8 else 'error' }}">{{ total_calls }}</div>
                <p style="margin-top: 10px; color: #94a3b8;">Success Rate: {{ "%.2f"|format(success_rate * 100) }}%</p>
            </div>
        </div>
        
        <h2 class="section-title">🤖 Agents</h2>
        <table>
            <thead>
                <tr>
                    <th>Status</th>
                    <th>Agent ID</th>
                    <th>Name</th>
                    <th>Version</th>
                    <th>Runtime</th>
                    <th>Capabilities</th>
                    <th>Last Seen</th>
                </tr>
            </thead>
            <tbody>
                {% for agent in agents %}
                <tr>
                    <td>
                        {% if agent.status == 'online' %}
                        <span class="status-indicator status-online"></span>
                        <span class="badge badge-online">Online</span>
                        {% elif agent.status == 'offline' %}
                        <span class="status-indicator status-offline"></span>
                        <span class="badge badge-offline">Offline</span>
                        {% else %}
                        <span class="status-indicator status-degraded"></span>
                        <span class="badge badge-degraded">{{ agent.status|title }}</span>
                        {% endif %}
                    </td>
                    <td><code>{{ agent.agent_id }}</code></td>
                    <td>{{ agent.display_name }}</td>
                    <td>{{ agent.version }}</td>
                    <td>{{ agent.runtime }}</td>
                    <td>{{ agent.capabilities|join(", ") }}</td>
                    <td>{{ agent.last_seen }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <h2 class="section-title">🛠️ Built-in Tools</h2>
        <table>
            <thead>
                <tr>
                    <th>Tool ID</th>
                    <th>Category</th>
                    <th>Provider</th>
                    <th>Capabilities</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                {% for tool in tools %}
                <tr>
                    <td><code>{{ tool.tool_id }}</code></td>
                    <td>{{ tool.category }}</td>
                    <td>{{ tool.provider }}</td>
                    <td>{{ tool.capabilities|join(", ") }}</td>
                    <td>
                        {% if tool.enabled %}
                        <span class="badge badge-online">Enabled</span>
                        {% else %}
                        <span class="badge badge-offline">Disabled</span>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        
        <h2 class="section-title">📊 Monitoring Endpoints</h2>
        <div class="endpoint-list">
            <div class="endpoint">GET /monitoring/dashboard</div>
            <div class="endpoint">GET /monitoring/metrics</div>
            <div class="endpoint">GET /monitoring/health</div>
            <div class="endpoint">GET /monitoring/status</div>
            <div class="endpoint">GET /monitoring/calls</div>
            <div class="endpoint">GET /metrics</div>
        </div>
        
        <footer style="margin-top: 40px; padding: 20px; text-align: center; color: #64748b;">
            <p>Fabric MCP Server - Universal Tool Server & Agent Gateway</p>
            <p style="font-size: 0.875rem; margin-top: 10px;">
                Built with ❤️ for AI Agent communication
            </p>
        </footer>
    </div>
</body>
</html>
"""


def get_dashboard_data(registry, metrics) -> Dict[str, Any]:
    """Gather data for the dashboard"""
    from datetime import datetime
    
    # Get agent stats
    agents = registry.list_agents()
    online_agents = sum(1 for a in agents if a.status.value == "online")
    offline_agents = sum(1 for a in agents if a.status.value == "offline")
    
    # Get tool stats
    if hasattr(registry, 'list_tools'):
        tools = registry.list_tools()
    else:
        tools = []
    
    tool_categories = len(set(t.get('category', 'unknown') for t in tools))
    
    # Format agent data for display
    agent_data = []
    for agent in agents:
        agent_data.append({
            "agent_id": agent.agent_id,
            "display_name": agent.display_name,
            "version": agent.version,
            "runtime": getattr(agent, 'runtime', 'mcp'),
            "status": agent.status.value,
            "capabilities": [c.name for c in agent.capabilities],
            "last_seen": "Just now" if agent.status.value == "online" else "Unknown"
        })
    
    # Format tool data
    tool_data = []
    for tool in tools[:20]:  # Limit to 20 for display
        tool_data.append({
            "tool_id": tool.get('tool_id', 'unknown'),
            "category": tool.get('category', 'general'),
            "provider": tool.get('provider', 'builtin'),
            "capabilities": [c.get('name', 'unknown') for c in tool.get('capabilities', [])],
            "enabled": tool.get('enabled', True)
        })
    
    return {
        "version": "af-mcp-0.1",
        "uptime": "24h 15m",  # Placeholder
        "total_agents": len(agents),
        "online_agents": online_agents,
        "offline_agents": offline_agents,
        "total_tools": len(tools),
        "tool_categories": tool_categories,
        "total_calls": 15420,  # Placeholder
        "success_rate": 0.987,  # Placeholder
        "agents": agent_data,
        "tools": tool_data
    }


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Human-readable monitoring dashboard"""
    from fastapi.templating import Jinja2Templates
    
    # Get data
    fabric = request.app.state.fabric
    data = get_dashboard_data(fabric.registry, None)
    
    # Simple template rendering (without Jinja2 dependency)
    html = DASHBOARD_TEMPLATE
    
    # Basic template substitution
    for key, value in data.items():
        if isinstance(value, (int, float)):
            html = html.replace(f"{{{{ {key} }}}}", str(value))
        elif isinstance(value, str):
            html = html.replace(f"{{{{ {key} }}}}", value)
    
    # Handle lists (simplified)
    html = html.replace("{{ agents }}", str(data["agents"]))
    html = html.replace("{{ tools }}", str(data["tools"]))
    
    return HTMLResponse(content=html)


@router.get("/metrics")
async def monitoring_metrics(request: Request):
    """Machine-readable metrics in JSON format"""
    from observability.metrics import get_metrics
    
    fabric = request.app.state.fabric
    metrics = get_metrics()
    
    # Get registry stats
    stats = fabric.registry.get_stats() if hasattr(fabric.registry, 'get_stats') else {}
    
    return JSONResponse(content={
        "timestamp": datetime.utcnow().isoformat(),
        "server": {
            "version": "af-mcp-0.1",
            "status": "healthy"
        },
        "registry": {
            "agents": {
                "total": stats.get("agents", {}).get("total", 0),
                "by_status": stats.get("agents", {}).get("by_status", {})
            },
            "tools": {
                "total": stats.get("tools", {}).get("total", 0)
            },
            "calls": {
                "total": stats.get("calls", {}).get("total", 0),
                "failed": stats.get("calls", {}).get("failed", 0),
                "success_rate": stats.get("calls", {}).get("success_rate", 1.0),
                "last_hour": stats.get("calls", {}).get("last_hour", 0)
            }
        }
    })


@router.get("/health")
async def monitoring_health(request: Request):
    """AI-optimized health check endpoint"""
    fabric = request.app.state.fabric
    
    # Check database connection if using PostgreSQL
    db_status = "ok"
    if hasattr(fabric.registry, 'database_url'):
        try:
            # Simple health check query
            stats = fabric.registry.get_stats()
            db_status = "ok"
        except Exception as e:
            db_status = f"error: {str(e)}"
    
    agents = fabric.registry.list_agents()
    online_agents = sum(1 for a in agents if a.status.value == "online")
    
    health = {
        "status": "healthy" if db_status == "ok" and online_agents > 0 else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": db_status,
            "agents": {
                "total": len(agents),
                "online": online_agents
            }
        },
        "metadata": {
            "version": "af-mcp-0.1",
            "registry_type": "postgres" if hasattr(fabric.registry, 'database_url') else "yaml"
        }
    }
    
    return JSONResponse(content=health)


@router.get("/status")
async def ai_status(request: Request):
    """Machine-readable status for AI agents"""
    """
    This endpoint is specifically designed for AI agents to consume.
    It provides a structured view of available capabilities.
    """
    fabric = request.app.state.fabric
    
    # Get all agents and their capabilities
    agents = fabric.registry.list_agents()
    agent_list = []
    for agent in agents:
        agent_list.append({
            "id": agent.agent_id,
            "name": agent.display_name,
            "status": agent.status.value,
            "capabilities": [
                {
                    "name": c.name,
                    "streaming": c.streaming,
                    "timeout_ms": c.max_timeout_ms
                }
                for c in agent.capabilities
            ],
            "trust_tier": agent.trust_tier.value
        })
    
    # Get all tools
    tools = []
    if hasattr(fabric.registry, 'list_tools'):
        all_tools = fabric.registry.list_tools()
        for tool in all_tools:
            tools.append({
                "id": tool.get('tool_id'),
                "category": tool.get('category'),
                "provider": tool.get('provider'),
                "available": tool.get('enabled', True)
            })
    
    return JSONResponse(content={
        "schema_version": "1.0",
        "timestamp": datetime.utcnow().isoformat(),
        "fabric_version": "af-mcp-0.1",
        "services": {
            "agents": {
                "count": len(agent_list),
                "available": [a for a in agent_list if a["status"] == "online"],
                "all": agent_list
            },
            "tools": {
                "count": len(tools),
                "available": tools
            }
        },
        "endpoints": {
            "mcp": "/mcp/call",
            "health": "/health",
            "monitoring": "/monitoring",
            "metrics": "/metrics"
        }
    })


@router.get("/calls")
async def recent_calls(request: Request, limit: int = 100):
    """Get recent call logs"""
    fabric = request.app.state.fabric
    
    if hasattr(fabric.registry, 'get_call_logs'):
        logs = fabric.registry.get_call_logs(limit=limit)
    else:
        logs = []
    
    return JSONResponse(content={
        "calls": logs,
        "count": len(logs)
    })

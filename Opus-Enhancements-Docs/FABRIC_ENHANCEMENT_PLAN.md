# Fabric A2A — Enhancement Roadmap & Frontend Integration Guide

## Current State Assessment

**What you have working:**
- Fabric MCP Server live at `fabric.perceptor.us` with 12 REST endpoints (Swagger docs confirmed)
- MCPFabric frontend at `mcpfabric.space` with Observatory, Registry, Console, and Playground pages
- Redis Streams + Pub/Sub message bus architecture
- PostgreSQL agent registry with capability-based routing
- 20+ built-in tools (IO, web, math, text, system, data, security)
- Redis ACL per-agent isolation
- One real agent: Aether Agent inside AetherOS

**What the frontend currently shows (mock data):**
- 35 Active Agents, 128,876K Messages/sec, 19 Active Ops, 37ms Avg Latency
- Observatory: 7 agents, 7 connections, 646 messages with force-directed graph visualization
- Agent types: Orchestrator, Worker, Gateway, Observer

---

## Phase 1: Wire Frontend to Real Data (Week 1-2)

### The Core Problem
Your frontend is gorgeous but hardcoded. You need API integration between `mcpfabric.space` and `fabric.perceptor.us`.

### Backend: Add CORS + WebSocket Support

Your Fabric server needs to allow cross-origin requests from mcpfabric.space. If you're using FastAPI:

```python
# server.py — add near the top
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://mcpfabric.space",
        "http://localhost:3000",  # local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Backend: Add Missing Endpoints for the Dashboard

The frontend needs a few aggregate endpoints your current API doesn't expose:

```python
# Add to server.py

@app.get("/mcp/stats")
async def get_stats():
    """Aggregate stats for the dashboard home page."""
    agents = await registry.list_agents()
    online = [a for a in agents if a.status == "online"]
    return {
        "active_agents": len(online),
        "total_agents": len(agents),
        "messages_total": await bus.get_message_count(),
        "messages_per_sec": await bus.get_throughput(),
        "active_ops": await bus.get_pending_count(),
        "avg_latency_ms": await bus.get_avg_latency(),
    }

@app.get("/mcp/agent/{agent_id}/messages")
async def get_agent_messages(agent_id: str, limit: int = 50):
    """Get recent messages for a specific agent (for Observatory)."""
    messages = await bus.receive_messages(agent_id, count=limit, block_ms=0)
    return {"agent_id": agent_id, "messages": messages}

@app.get("/mcp/connections")
async def get_connections():
    """Get agent-to-agent message flow data (for Observatory graph)."""
    # Query Redis streams for recent message patterns
    flows = await bus.get_message_flows(window_seconds=3600)
    return {"connections": flows, "window": "1h"}
```

### Backend: Add WebSocket for Live Observatory

```python
# Add real-time WebSocket for the Observatory "Live" indicator
from fastapi import WebSocket

@app.websocket("/ws/observatory")
async def observatory_ws(websocket: WebSocket):
    await websocket.accept()
    pubsub = bus.redis.pubsub()
    await pubsub.psubscribe("agent.*")
    try:
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                await websocket.send_json({
                    "type": "message",
                    "channel": message["channel"].decode(),
                    "data": json.loads(message["data"]),
                    "timestamp": datetime.utcnow().isoformat(),
                })
    except Exception:
        pass
    finally:
        await pubsub.unsubscribe()
```

### Frontend: Replace Mock Data with API Calls

In your MCPFabric frontend, replace hardcoded values with fetch calls:

```typescript
// lib/api.ts — Create a centralized API client
const FABRIC_API = process.env.NEXT_PUBLIC_FABRIC_URL || "https://fabric.perceptor.us";

export async function fetchStats() {
  const res = await fetch(`${FABRIC_API}/mcp/stats`);
  return res.json();
}

export async function fetchAgents() {
  const res = await fetch(`${FABRIC_API}/mcp/list_agents`);
  return res.json();
}

export async function fetchConnections() {
  const res = await fetch(`${FABRIC_API}/mcp/connections`);
  return res.json();
}

// WebSocket for live Observatory
export function connectObservatory(onMessage: (data: any) => void) {
  const ws = new WebSocket(`wss://fabric.perceptor.us/ws/observatory`);
  ws.onmessage = (event) => onMessage(JSON.parse(event.data));
  return ws;
}
```

```tsx
// components/Dashboard.tsx — Replace hardcoded stats
import { useEffect, useState } from 'react';
import { fetchStats } from '@/lib/api';

export function DashboardStats() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    fetchStats().then(setStats);
    // Refresh every 5 seconds
    const interval = setInterval(() => fetchStats().then(setStats), 5000);
    return () => clearInterval(interval);
  }, []);

  if (!stats) return <LoadingSkeleton />;

  return (
    <div className="grid grid-cols-4 gap-4">
      <StatCard label="Active Agents" value={stats.active_agents} />
      <StatCard label="Messages/sec" value={formatNumber(stats.messages_per_sec)} />
      <StatCard label="Active Ops" value={stats.active_ops} />
      <StatCard label="Avg Latency" value={`${stats.avg_latency_ms}ms`} />
    </div>
  );
}
```

---

## Phase 2: SDK & Developer Experience (Week 2-3)

### Publish the Python SDK

I've created a complete Python SDK (`fabric_a2a_sdk.py`) — here's how to ship it:

```bash
# Directory structure
fabric-a2a-sdk/
├── pyproject.toml
├── SDK_README.md → README.md
├── fabric_a2a_sdk.py → src/fabric_a2a_sdk/__init__.py
└── tests/
    └── test_client.py

# Publish to PyPI
pip install build twine
python -m build
twine upload dist/*
```

### Add a JavaScript/TypeScript SDK

For frontend and Node.js agent developers:

```typescript
// fabric-a2a-sdk/index.ts (simplified)
export class FabricClient {
  constructor(
    private baseUrl: string,
    private apiKey: string
  ) {}

  async registerAgent(config: AgentConfig): Promise<void> {
    await this.post('/mcp/register_agent', config);
  }

  async callAgent(agentId: string, capability: string, task: string): Promise<any> {
    return this.post('/mcp/call', {
      name: 'fabric.call',
      arguments: { agent_id: agentId, capability, task }
    });
  }

  private async post(path: string, body: any): Promise<any> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new FabricError(res.status, await res.text());
    return res.json();
  }
}
```

### Add an Agent Card (A2A Protocol Compatibility)

Google's A2A protocol is gaining massive traction (150+ orgs, Linux Foundation governance). Add an agent card endpoint to make Fabric agents discoverable by any A2A-compatible system:

```python
# Add to server.py — A2A Agent Card discovery
@app.get("/.well-known/agent.json")
async def agent_card():
    """A2A-compatible agent card for Fabric gateway."""
    return {
        "name": "Fabric A2A Gateway",
        "description": "Multi-agent orchestration gateway with MCP tools",
        "url": "https://fabric.perceptor.us",
        "version": "0.1.0",
        "capabilities": {
            "streaming": True,
            "pushNotifications": False,
        },
        "skills": [
            {
                "id": "delegate-task",
                "name": "Delegate Task",
                "description": "Route a task to a specialized agent",
            },
            {
                "id": "tool-execution",
                "name": "Tool Execution",
                "description": "Execute 20+ built-in tools (IO, web, math, text)",
            },
        ],
        "authentication": {
            "schemes": ["bearer"],
        },
    }
```

---

## Phase 3: Production Hardening (Week 3-4)

### Add Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/mcp/call")
@limiter.limit("100/minute")
async def mcp_call(request: Request, body: dict):
    ...
```

### Add Request Logging / Audit Trail

```python
import structlog

logger = structlog.get_logger()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    elapsed = (time.monotonic() - start) * 1000

    logger.info(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round(elapsed, 2),
        agent=request.headers.get("X-Agent-ID", "unknown"),
    )
    return response
```

### Add Agent Heartbeat System

```python
# Agents ping this endpoint periodically to stay "online"
@app.post("/mcp/agent/{agent_id}/heartbeat")
async def agent_heartbeat(agent_id: str):
    await registry.update_last_seen(agent_id)
    return {"status": "ok", "agent_id": agent_id}

# Background task to mark stale agents as offline
@app.on_event("startup")
async def start_health_checker():
    async def check_health():
        while True:
            await asyncio.sleep(30)
            agents = await registry.list_agents()
            for agent in agents:
                if agent.last_seen and (now - agent.last_seen).seconds > 60:
                    await registry.update_status(agent.agent_id, "offline")
    asyncio.create_task(check_health())
```

---

## Phase 4: Multi-Tenant & Scale (Month 2)

### Add Tenant Isolation

```python
# Each organization gets a tenant prefix
# Keys become: tenant:{tenant_id}:agent:{agent_id}:inbox
# This lets you run MCPFabric as a hosted platform

@app.post("/mcp/tenant/create")
async def create_tenant(name: str, plan: str = "free"):
    tenant_id = generate_tenant_id()
    api_key = generate_api_key()
    await db.create_tenant(tenant_id, name, plan, api_key)
    return {"tenant_id": tenant_id, "api_key": api_key}
```

### Frontend: Add Tenant Switcher

Your Observatory already has a "Production" dropdown and "All Tenants" filter — wire these to real tenant data.

---

## What to Tell People with Agents

Here's the pitch and onboarding flow for external developers:

### The 30-Second Pitch

> "Fabric A2A is the message bus for AI agents. Register your agent, and it can discover and delegate tasks to any other agent on the network. Built on Redis Streams for reliable async messaging, MCP for tool access, and PostgreSQL for agent discovery. Think of it as a service mesh, but for AI agents."

### The Onboarding Flow

1. **Get an API key** from mcpfabric.space (or from you directly for now)
2. **Install the SDK**: `pip install fabric-a2a`
3. **Register their agent** (3 lines of code)
4. **Start sending/receiving messages** (2 lines of code)
5. **View their agent** in the Observatory at mcpfabric.space/observatory

### What Makes This Different from Google's A2A

Google's A2A requires every agent to implement the full protocol spec (Agent Cards, JSON-RPC, SSE). Fabric A2A is simpler:
- Your agents talk to the **Fabric gateway** via simple HTTP
- The gateway handles routing, discovery, and message persistence
- No need to implement the full A2A spec — just POST to `/mcp/call`
- Built-in tools mean agents don't need to reinvent file I/O, HTTP, math, etc.
- Redis Streams give you reliable message persistence that pure A2A doesn't have

You can position this as: **"A2A is the protocol. Fabric is the infrastructure."**

---

## Priority Actions (This Weekend)

1. ☐ Run `test_endpoints.sh` against `fabric.perceptor.us` to see what's working
2. ☐ Add CORS to your Fabric server for `mcpfabric.space`
3. ☐ Add `/mcp/stats` endpoint for dashboard home page
4. ☐ Add `/.well-known/agent.json` for A2A compatibility
5. ☐ Replace one mock component on the frontend with real API data
6. ☐ Register Aether Agent via the SDK or curl
7. ☐ Ship the Python SDK to PyPI (even as 0.1.0-alpha)

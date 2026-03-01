# Fabric A2A - Technical Architecture Document

**Version:** 1.0
**Date:** March 2026
**Project:** fabric_a2a

---

## 1. Executive Summary

Fabric A2A is a model-agnostic, agent-agnostic message passing system for coordinating AI agents. Built on the Model Context Protocol (MCP), it enables any AI agent to discover, communicate, and delegate tasks to other agents through a unified message bus.

### Key Capabilities
- **Async Messaging**: Redis Streams for persistent task queues
- **Real-time Events**: Pub/Sub for broadcasts and notifications
- **Agent Registry**: PostgreSQL-backed discovery service
- **Built-in Tools**: 20+ tools for file I/O, HTTP, math, text, and more
- **ACL Security**: Fine-grained permissions per agent

---

## 2. System Architecture

### 2.1 High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Agent Layer                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  Percy   │  │  Coder   │  │  Vision  │  │  Memory  │      │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘      │
└───────┼──────────────┼──────────────┼──────────────┼──────────┘
        │              │              │              │
        └──────────────┴──────────────┴──────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Fabric A2A Gateway                            │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐     │
│  │   MCP Server   │  │ Message Bus    │  │   Registry    │     │
│  │   (HTTP/WS)    │  │(Redis Streams)│  │  (PostgreSQL) │     │
│  └────────────────┘  └────────────────┘  └────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        ▼                      ▼                      ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ Redis Streams│      │  Redis Pub/Sub│      │ PostgreSQL   │
│ (Task Queues)│      │  (Events)     │      │ (Registry)   │
└──────────────┘      └──────────────┘      └──────────────┘
```

### 2.2 Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Server Framework | FastAPI | 0.109.0 |
| ASGI Server | Uvicorn | 0.27.0 |
| Message Broker | Redis | 7.0+ (with Streams) |
| Database | PostgreSQL | 14+ |
| SDK Languages | Python | 3.11+ |
| Observability | Prometheus + Grafana | Latest |

---

## 3. Core Components

### 3.1 MCP Server (`server.py`)

The MCP Server is the central gateway that exposes all Fabric functionality via HTTP/WebSocket using the Model Context Protocol.

**Location:** `server.py` (60,869 bytes)

**Key Features:**
- HTTP and WebSocket transport support
- MCP protocol implementation
- Tool execution via `fabric.tool.call`
- Agent delegation via `fabric.call`
- Message bus operations via `fabric.message.*`
- Distributed tracing with trace_id/span_id

**Key Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/mcp/call` | POST | Execute a tool or delegate to agent |
| `/mcp/list_agents` | GET | List registered agents |
| `/mcp/list_tools` | GET | List available tools |
| `/mcp/register_agent` | POST | Register a new agent |
| `/health` | GET | Health check |
| `/metrics` | GET | Prometheus metrics |

**MCP Tools Exposed:**
```python
# Agent Communication
- fabric.call                    # Delegate task to agent
- fabric.agent.list             # List registered agents
- fabric.agent.describe         # Get agent details

# Tool Execution
- fabric.tool.list              # List available tools
- fabric.tool.call              # Execute built-in tool
- fabric.tool.info             # Get tool information

# Async Messaging
- fabric.message.send           # Send message to agent queue
- fabric.message.receive       # Receive messages from queue
- fabric.message.publish       # Publish to topic
- fabric.message.subscribe      # Subscribe to topics
- fabric.message.acknowledge   # Acknowledge message
- fabric.message.queue_status  # Get queue depth
```

### 3.2 Message Bus (`fabric_message_bus.py`)

Async agent-to-agent communication using Redis Streams and Pub/Sub.

**Location:** `fabric_message_bus.py` (19,438 bytes)

**Architecture:**
- **Streams**: Persistent task queues (`agent:{id}:inbox`)
- **Pub/Sub**: Real-time broadcasts (`agent.{id}.new_message`, `shared:*`)
- **Consumer Groups**: Load balancing across agent replicas

**Key Classes:**

```python
# Message Format
@dataclass
class FabricMessage:
    id: str                      # Unique message ID
    from_agent: str              # Sender agent ID
    to_agent: str                # Receiver agent ID
    message_type: str            # task, response, event, heartbeat
    payload: Dict[str, Any]      # Message content
    timestamp: str               # ISO format timestamp
    priority: int                # 1-4 (LOW to URGENT)
    ttl_seconds: int             # Time to live (default 24h)
    reply_to: Optional[str]      # Response queue
    correlation_id: Optional[str] # For conversation tracking

class FabricMessageBus:
    """Async message bus for agent-to-agent communication"""

    # Direct Messaging
    async def send_message(message: FabricMessage) -> Dict
    async def receive_messages(agent_id: str, count: int, block_ms: int) -> List
    async def acknowledge_message(agent_id: str, stream_id: str) -> bool

    # Pub/Sub
    async def publish(topic: str, message: Dict) -> int
    async def subscribe(topics: List[str], callback: Callable) -> None

    # Utility
    async def get_queue_depth(agent_id: str) -> int
    async def get_stream_info(agent_id: str) -> Dict

class FabricMessageBusMCP:
    """MCP tool wrapper for message bus operations"""
```

**Redis Key Patterns:**
| Pattern | Type | Purpose |
|---------|------|---------|
| `agent:{agent_id}:inbox` | Stream | Task queue for each agent |
| `agent:{agent_id}:results` | Stream | Response queue |
| `shared:{topic}` | Key | Shared state |
| `agent.{agent_id}.new_message` | Pub/Sub | Per-agent notifications |

### 3.3 Tool System (`tools/`)

Plugin-based tool infrastructure with auto-discovery.

**Directory Structure:**
```
tools/
├── __init__.py
├── base.py                    # BaseTool class and registry
├── builtin_tools.py           # Legacy compatibility layer
├── registry.yaml              # Tool metadata registry
└── plugins/
    ├── __init__.py
    ├── TEMPLATE.py            # Tool creation template
    ├── builtin_io.py         # File I/O tools
    ├── builtin_web.py        # HTTP requests, web scraping
    ├── builtin_math.py       # Calculator, statistics
    ├── builtin_text.py       # Regex, transform, diff
    ├── builtin_system.py     # Execute, env vars
    ├── builtin_data.py       # JSON, CSV, validation
    ├── builtin_security.py   # Hash, base64
    ├── builtin_encode.py     # URL encoding
    ├── builtin_docs.py       # Markdown processing
    └── custom/               # Custom user tools
        └── webhook_notifications.py
```

**Tool Categories:**

| Category | Tool IDs | Description |
|----------|----------|-------------|
| `io` | read_file, write_file, list_directory, search_files | File system operations |
| `web` | http_request, fetch_page, parse_url, brave_search | Web/HTTP operations |
| `math` | calculate, statistics | Mathematical operations |
| `text` | regex, transform, diff | Text processing |
| `system` | execute, env, datetime | System operations |
| `data` | json, csv, validate | Data processing |
| `security` | hash, base64 | Security utilities |
| `encode` | url_encode | Encoding utilities |
| `docs` | markdown | Documentation processing |

**BaseTool Class:**
```python
class BaseTool(ABC):
    """Base class for all Fabric tools"""

    _registry: Dict[str, Type['BaseTool']] = {}  # Tool registry
    _instances: Dict[str, 'BaseTool'] = {}         # Singleton instances

    TOOL_ID: str = None           # Unique identifier (e.g., "io.read_file")
    CAPABILITIES: Dict[str, str] = {}  # capability -> method mapping

    @classmethod
    def register(cls, tool_class: Type['BaseTool']):
        """Register tool class in registry"""

    @classmethod
    def load_plugins(cls, plugins_dir: str):
        """Auto-discover and load plugins"""

    async def execute_capability(self, capability: str, **kwargs) -> ToolResult:
        """Execute a capability by name"""
```

**Tool Plugin Pattern:**
```python
class MyTool(BaseTool):
    TOOL_ID = "category.tool_name"
    CAPABILITIES = {
        "capability_name": "method_name"
    }

    async def method_name(self, param1: str, **kwargs) -> ToolResult:
        """Tool implementation"""
        return ToolResult({"result": "data"})

# Auto-register
BaseTool.register(MyTool)
```

### 3.4 Agent Registry (`database/`)

PostgreSQL-backed agent discovery and management.

**Location:** `database/models.py`, `database/postgres_registry.py`

**Database Schema:**

```python
# Core Tables
class Agent(Base):
    """Agent registration"""
    id: UUID (PK)
    agent_id: str (unique)
    display_name: str
    version: str
    description: Text
    runtime: str (default: "mcp")
    transport: str (http/stdio)
    endpoint_uri: str
    status: Enum (ONLINE/OFFLINE/DEGRADED/UNKNOWN)
    trust_tier: Enum (LOCAL/ORG/PUBLIC)
    tags: Array[str]
    created_at, updated_at, last_seen_at: DateTime

class Capability(Base):
    """Agent capabilities"""
    id: UUID (PK)
    agent_id: UUID (FK)
    name: str
    description: Text
    streaming: bool
    modalities: Array[str]
    input_schema: JSON
    output_schema: JSON
    max_timeout_ms: int

class Tool(Base):
    """Built-in tools registry"""
    id: UUID (PK)
    tool_id: str (unique)
    display_name: str
    provider: str (builtin/agent/external)
    category: str
    trust_tier: Enum
    config: JSON
    enabled: bool

class HealthCheck(Base):
    """Agent health history"""
    agent_id: UUID (FK)
    status: Enum
    latency_ms: Float
    error_message: Text
    checked_at: DateTime

class AgentMetrics(Base):
    """Agent usage metrics"""
    agent_id: UUID (FK)
    total_calls, successful_calls, failed_calls: Int
    avg_latency_ms, min_latency_ms, max_latency_ms: Float
    p95_latency_ms, p99_latency_ms: Float
    period_start, period_end: DateTime
    granularity: str (minute/hour/day)

class CallLog(Base):
    """Detailed call logs"""
    trace_id: str (indexed)
    span_id: str
    principal_id: str
    target_type: str (agent/tool)
    target_id: str
    input_payload, output_payload: JSON
    error_code, error_message: str
    started_at, completed_at: DateTime
    duration_ms: Float
    status: str
```

### 3.5 Python SDK (`sdk/python/`)

Client libraries for interacting with Fabric.

**Location:** `sdk/python/fabric_a2a/`

**Package Structure:**
```
sdk/python/
├── fabric_a2a/
│   ├── __init__.py
│   ├── client.py         # Sync and async clients
│   ├── models.py         # Pydantic models
│   ├── tools.py          # Tool client
│   ├── agents.py         # Agent client
│   └── exceptions.py     # Custom exceptions
├── pyproject.toml        # Package configuration
└── README.md
```

**Client Usage:**
```python
from fabric_a2a import FabricClient, AsyncFabricClient

# Synchronous
client = FabricClient(
    base_url="http://localhost:8000",
    token="your-token"
)
result = client.call("fabric.tool.call", {
    "tool_id": "io.read_file",
    "capability": "read",
    "parameters": {"path": "./file.txt"}
})

# Asynchronous
async with AsyncFabricClient(base_url="...", token="...") as client:
    result = await client.call("fabric.tool.call", {...})
```

---

## 4. Infrastructure

### 4.1 Docker Compose Services

**Location:** `docker-compose.yml`

```yaml
services:
  postgres:
    image: postgres:16-alpine
    ports: 5432
    volumes: postgres_data
    environment: POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB

  redis-stack:
    image: redis/redis-stack:latest
    ports: 6379 (Redis), 8001 (RedisInsight)
    volumes: fabric_redis_data, ./config/redis/users.acl
    environment: REDIS_ARGS (with ACL and persistence)

  fabric-gateway:
    build: .
    ports: 8000
    environment: FABRIC_*, DATABASE_URL, REDIS_URL
    depends_on: postgres, redis-stack

  prometheus:     # Optional - monitoring profile
  grafana:       # Optional - monitoring profile
```

### 4.2 Redis ACL Configuration

**Location:** `config/redis/users.acl`

Per-agent access control:
```acl
# Agent-specific permissions
user percy on >percy_secret ~agent:percy:* ~shared:* +@stream +@pubsub +@read &shared:* &agent.percy:*
user coder on >coder_secret ~agent:coder:* ~shared:* +@stream +@pubsub +@read &shared:* &agent.coder:*

# Server has full access
user fabric_mcp on >mcp_secret ~agent:* +@stream +@pubsub +@read &*
```

### 4.3 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FABRIC_TRANSPORT` | http or stdio | http |
| `FABRIC_PORT` | Server port | 8000 |
| `FABRIC_ADMIN_KEY` | Admin key for `/admin/*` key management endpoints | none |
| `DATABASE_URL` | PostgreSQL connection | postgresql://... |
| `REDIS_URL` | Redis connection | redis://localhost:6379 |
| `USE_POSTGRES` | Enable PostgreSQL | true |
| `ENABLE_METRICS` | Enable Prometheus | true |
| `LOG_LEVEL` | Logging level | INFO |

---

## 5. Deployment

### 5.1 Production Requirements

| Requirement | Specification |
|-------------|---------------|
| Python | 3.11+ |
| Redis | 7.0+ (with Streams support) |
| PostgreSQL | 14+ |
| Memory | 512MB minimum, 2GB recommended |
| CPU | 0.5 cores minimum |

### 5.2 Production Checklist

1. **Security**
   - [ ] Set `FABRIC_ADMIN_KEY` in environment
   - [ ] Provision at least one `fab_sk_live_...` API key via `/admin/keys`
   - [ ] Configure Redis ACL for each agent
   - [ ] Enable PostgreSQL for production registry
   - [ ] Configure CORS properly

2. **Monitoring**
   - [ ] Enable Prometheus metrics
   - [ ] Set up Grafana dashboards
   - [ ] Configure log aggregation

3. **Scaling**
   - [ ] Use consumer groups for horizontal scaling
   - [ ] Configure Redis persistence (AOF)
   - [ ] Set up PostgreSQL connection pooling

---

## 6. Current State Assessment

### 6.1 Implemented Features

| Feature | Status | Location |
|---------|--------|----------|
| MCP Server (HTTP) | ✅ Stable | server.py |
| Message Bus (Redis Streams) | ✅ Stable | fabric_message_bus.py |
| Tool Plugin System | ✅ Stable | tools/base.py, tools/plugins/ |
| PostgreSQL Registry | ✅ Stable | database/postgres_registry.py |
| Python SDK | ✅ Stable | sdk/python/ |
| Docker Compose | ✅ Stable | docker-compose.yml |
| Redis ACL | ✅ Stable | config/redis/users.acl |
| Prometheus Metrics | ✅ Stable | server.py |
| Health Endpoints | ✅ Stable | server.py |

### 6.2 Known Issues / Technical Debt

Based on the codebase analysis:

1. **server.py** - Single monolithic file (60KB+) that could benefit from modularization
2. **Dual Server Files** - Both `server.py` and `server_new.py` exist
3. **Documentation** - Multiple README files (README.md, README-Legacy.md)
4. **Plugin Loading** - Uses synchronous importlib in async context
5. **Consumer Groups** - Implementation exists but may need testing
6. **Delivery Confirmation** - TODO comment for `wait_for_delivery` in message bus

### 6.3 Architecture Refactoring

The [ARCHITECTURE_REFACTOR.md](ARCHITECTURE_REFACTOR.md) outlines a 3-layer architecture proposal:

1. **Layer 1**: Fabric Gateway Core (MCP Router, Registry, Plugin Manager)
2. **Layer 2**: Tool Layer (pluggable built-in and external tools)
3. **Layer 3**: Skills Layer (future - composable workflows)

---

## 7. API Reference

### 7.1 MCP Tool Calls

**Execute Tool:**
```json
{
  "name": "fabric.tool.call",
  "arguments": {
    "tool_id": "io.read_file",
    "capability": "read",
    "parameters": {"path": "./file.txt"}
  }
}
```

**Delegate to Agent:**
```json
{
  "name": "fabric.call",
  "arguments": {
    "agent_id": "percy",
    "capability": "reason",
    "task": "Analyze the pros and cons of microservices"
  }
}
```

**Send Message:**
```json
{
  "name": "fabric.message.send",
  "arguments": {
    "from_agent": "coder",
    "to_agent": "percy",
    "message_type": "task",
    "payload": {"task_type": "code_review", "pr_id": "123"},
    "priority": "high"
  }
}
```

---

## 8. Testing

### 8.1 Test Files

| File | Purpose |
|------|---------|
| `quick_test.py` | Quick integration tests |
| `example_client.py` | SDK usage examples |
| `TESTING_PLAYBOOK.md` | Detailed testing procedures |

### 8.2 Running Tests

```bash
# Unit tests
pytest

# Integration tests
python quick_test.py

# With Docker
docker-compose up -d
python example_client.py
```

---

## 9. Dependencies

**Core:**
- fastapi==0.109.0
- uvicorn[standard]==0.27.0
- pydantic==2.5.3
- pyyaml==6.0.1

**Async:**
- asyncio==3.4.3
- aiohttp==3.9.1
- redis[hiredis]==5.0.0  # (implied by redis.asyncio)

**Database:**
- psycopg2-binary==2.9.9
- sqlalchemy==2.0.25

**Observability:**
- prometheus-client==0.19.0
- structlog==24.1.0

**Tools:**
- beautifulsoup4==4.12.3
- markdown==3.5.2
- jsonschema==4.21.1

---

## 10. File Inventory

### Source Files
| File | Size | Purpose |
|------|------|---------|
| `server.py` | 60.8KB | MCP HTTP/WS server |
| `fabric_message_bus.py` | 19.4KB | Redis Streams/Pub/Sub messaging |
| `database/models.py` | 10.3KB | SQLAlchemy models |
| `database/postgres_registry.py` | 9.8KB | PostgreSQL registry |
| `tools/base.py` | 7.2KB | BaseTool class |
| `tools/builtin_tools.py` | 4.2KB | Tool exports |

### Configuration Files
| File | Purpose |
|------|---------|
| `docker-compose.yml` | Multi-service orchestration |
| `docker-compose.redis.yml` | Redis standalone |
| `agents.yaml` | Agent registry config |
| `requirements.txt` | Python dependencies |
| `.env` / `.env.example` | Environment variables |

### Documentation
| File | Purpose |
|------|---------|
| `README.md` | Main documentation |
| `ARCHITECTURE_REFACTOR.md` | Refactoring proposal |
| `DEPLOYMENT.md` | Deployment guide |
| `INTEGRATION_GUIDE_FOR_AGENTS.md` | Agent integration |
| `SPEC.md` | Technical specification |

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| MCP | Model Context Protocol - JSON-RPC based protocol for AI agent communication |
| A2A | Agent-to-Agent - Direct communication between agents |
| Consumer Group | Redis feature for load balancing message consumption |
| Trust Tier | Security level (LOCAL, ORG, PUBLIC) for agent access |
| Stream | Redis data structure for ordered message storage |
| Pub/Sub | Redis publish/subscribe for real-time events |
| PSK | Pre-Shared Key for authentication |

---

*Document generated from codebase analysis*
*Last updated: March 2026*

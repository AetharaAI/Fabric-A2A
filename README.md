# Fabric A2A - Agent-to-Agent Communication Framework

A model-agnostic, agent-agnostic message passing system for coordinating AI agents using Redis Streams, Pub/Sub, and MCP as the interface.

## Overview

Fabric A2A enables any AI agent to discover, communicate, and delegate tasks to other agents through a unified message bus. Built on the Model Context Protocol (MCP), it provides:

- **Async Messaging** - Redis Streams for persistent task queues
- **Real-time Events** - Pub/Sub for broadcasts and notifications
- **Agent Registry** - PostgreSQL-backed discovery service
- **Built-in Tools** - 20+ tools for file I/O, HTTP, math, text, and more
- **ACL Security** - Fine-grained permissions per agent

## Architecture

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
│  │   (HTTP/WS)    │  │ (Redis Streams)│  │  (PostgreSQL) │     │
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

## Components

### Message Bus (`fabric_message_bus.py`)

Async A2A communication using Redis Streams and Pub/Sub:

```python
from fabric_message_bus import FabricMessageBus, MessagePriority

bus = FabricMessageBus(redis_url="redis://localhost:6379")

# Send task to agent
await bus.send_task(
    from_agent="coder",
    to_agent="percy",
    task_type="code_review",
    payload={"pr_id": "123", "files": ["main.py"]},
    priority=MessagePriority.HIGH
)

# Receive messages
messages = await bus.receive_messages("percy", count=5, block_ms=10000)

# Publish event
await bus.publish("analytics.insights", {"pattern": "unusual_traffic"})
```

### MCP Server (`server.py`)

HTTP/WebSocket server exposing MCP tools:

- `fabric.call` - Delegate task to an agent
- `fabric.agent.list` - List registered agents
- `fabric.agent.describe` - Get agent details
- `fabric.tool.list` - List available tools
- `fabric.tool.call` - Execute built-in tool
- `fabric.message.*` - Async messaging operations

### Agent Registry (`database/postgres_registry.py`)

PostgreSQL-backed agent discovery:

- Agent registration and health monitoring
- Capability-based routing
- Trust tier management
- Call logging and metrics

### Tool System (`tools/`)

Plugin-based tool infrastructure:

```
tools/
├── base.py          # BaseTool class and registry
├── builtin_tools.py # Legacy compatibility layer
└── plugins/
    ├── builtin_io.py        # File I/O
    ├── builtin_web.py       # HTTP requests
    ├── builtin_math.py      # Calculator, statistics
    ├── builtin_text.py      # Regex, transform, diff
    ├── builtin_system.py    # Execute, env vars
    ├── builtin_data.py      # JSON, CSV, validation
    ├── builtin_security.py  # Hash, base64
    ├── builtin_encode.py    # URL encoding
    └── builtin_docs.py      # Markdown processing
```

## Redis Configuration

### ACL Permissions (`config/redis/users.acl`)

Per-agent access control:

```acl
# Percy Agent - Reasoning
user percy on >percy_secret ~agent:percy:* ~shared:* +@stream +@pubsub +@read &shared:* &agent.percy:*

# Coder Agent - Code generation
user coder on >coder_secret ~agent:coder:* ~shared:* +@stream +@pubsub +@read &shared:* &agent.coder:*

# Fabric MCP Server - Full access
user fabric_mcp on >mcp_secret ~agent:* +@stream +@pubsub +@read &*
```

### Streams Pattern

- `agent:{agent_id}:inbox` - Task queue for each agent
- `shared:{topic}` - Shared state keys

### Pub/Sub Channels

- `agent.{agent_id}.new_message` - Per-agent notifications
- `shared:*` - Shared event topics

## Quick Start

### Prerequisites

- Python 3.11+
- Redis 7.0+
- PostgreSQL 14+

### Installation

```bash
cd fabric
pip install -r requirements.txt
```

### Configuration

```bash
# Set environment variables
export REDIS_URL="redis://localhost:6379"
export DATABASE_URL="postgresql://user:pass@localhost:5432/fabric"
export MASTER_SECRET="your-secret"
```

### Running

```bash
# Start MCP server (HTTP)
python server.py --transport http --port 8000

# Start with stdio transport
python server.py --transport stdio
```

## MCP Tools Reference

### Agent Communication

```json
{
  "name": "fabric.call",
  "arguments": {
    "agent_id": "percy",
    "capability": "reason",
    "task": "Analyze the pros and cons of microservices",
    "context": {"domain": "software architecture"},
    "stream": false,
    "timeout_ms": 60000
  }
}
```

### Tool Execution

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

### Async Messaging

```json
{
  "name": "fabric.message.send",
  "arguments": {
    "from_agent": "coder",
    "to_agent": "percy",
    "message_type": "task",
    "payload": {"task_type": "code_review", "pr_id": "123"}
  }
}
```

## Agent Registration

Agents register via the MCP protocol:

```bash
curl -X POST http://localhost:8000/mcp/register_agent \
  -H "Authorization: Bearer $MASTER_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "my-agent",
    "display_name": "My Agent",
    "version": "1.0.0",
    "capabilities": [
      {"name": "process", "description": "Process data"}
    ],
    "endpoint": {"transport": "http", "uri": "http://localhost:9000/mcp"}
  }'
```

## Project Structure

```
fabric/
├── server.py              # MCP HTTP/WS server
├── server_new.py          # Updated server implementation
├── fabric_message_bus.py  # Redis Streams/Pub/Sub messaging
├── config/
│   └── redis/
│       └── users.acl      # Redis ACL configuration
├── database/
│   ├── models.py          # SQLAlchemy models
│   └── postgres_registry.py  # PostgreSQL registry backend
├── tools/
│   ├── base.py            # BaseTool class
│   ├── builtin_tools.py   # Tool exports
│   └── plugins/           # Tool implementations
├── sdk/
│   └── python/            # Python SDK
└── observability/         # Metrics and monitoring
```

## Security

### Redis ACL

Agents are isolated by ACL:
- Key pattern: `~agent:{agent_id}:*` - Own streams only
- Channel pattern: `&shared:*` - Shared topics only
- Commands: `+@stream` (XADD/XREADGROUP), `+@pubsub` (PUBLISH/SUBSCRIBE)

### Authentication

- PSK for development
- Agent Passport (Ed25519 signatures) for production

## Monitoring

### Health Endpoints

```bash
curl http://localhost:8000/health
```

### Metrics

Prometheus metrics available at `/metrics`:
- `fabric_calls_total` - Total calls by agent
- `fabric_messages_sent` - Messages via message bus
- `fabric_agent_online` - Online agent count

## License

MIT

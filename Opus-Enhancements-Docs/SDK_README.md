# Fabric A2A Python SDK

> Connect your AI agent to the **Fabric A2A** message bus in under 5 minutes.

Fabric A2A is a model-agnostic, agent-agnostic message passing system for coordinating AI agents. This SDK gives you a clean Python interface to register agents, delegate tasks, send async messages, and call built-in tools — all through a single HTTP gateway.

## Install

```bash
# Minimal (uses stdlib urllib — zero dependencies)
pip install fabric-a2a

# Recommended (uses httpx for better performance + connection pooling)
pip install "fabric-a2a[httpx]"
```

## Quick Start

```python
from fabric_a2a_sdk import FabricClient

# Connect to your Fabric server
client = FabricClient(
    base_url="https://fabric.perceptor.us",
    api_key="your-api-key"
)

# Check connectivity
assert client.ping(), "Server unreachable!"

# Register your agent
client.register_agent(
    agent_id="my-agent",
    display_name="My Custom Agent",
    capabilities=[
        {"name": "summarize", "description": "Summarize documents"},
        {"name": "translate", "description": "Translate between languages"},
    ],
    endpoint="http://my-server:9000/mcp",
)

# Delegate a task to another agent
result = client.call_agent(
    agent_id="aether-agent",
    capability="reason",
    task="Analyze the pros and cons of microservices vs monoliths",
)
print(result.result)

# Send an async message
client.send_message(
    from_agent="my-agent",
    to_agent="aether-agent",
    payload={"task_type": "review", "document_id": "doc-123"},
)

# Read your inbox
messages = client.receive_messages("my-agent", count=10)
for msg in messages:
    print(f"From {msg.from_agent}: {msg.payload}")

client.close()
```

## Using as a Context Manager

```python
with FabricClient("https://fabric.perceptor.us", "your-key") as client:
    agents = client.list_agents()
    for agent in agents:
        print(f"{agent.agent_id}: {agent.status}")
```

## API Reference

### Connection & Health

| Method | Description |
|--------|-------------|
| `client.ping()` | Returns `True` if server is reachable |
| `client.health()` | Full health check response |
| `client.mcp_health()` | MCP subsystem health |
| `client.metrics()` | Prometheus metrics (raw text) |
| `client.wait_for_server(timeout=30)` | Block until server is up |

### Agent Registry

| Method | Description |
|--------|-------------|
| `client.register_agent(agent_id, display_name, capabilities, endpoint)` | Register your agent |
| `client.list_agents()` | List all registered agents → `list[AgentInfo]` |
| `client.get_agent(agent_id)` | Get specific agent details → `AgentInfo` |

### Agent-to-Agent Calls

| Method | Description |
|--------|-------------|
| `client.call_agent(agent_id, capability, task, context?, timeout_ms?)` | Delegate a task → `CallResult` |

### Async Messaging

| Method | Description |
|--------|-------------|
| `client.send_message(from_agent, to_agent, payload, message_type?, priority?)` | Send async message |
| `client.receive_messages(agent_id, count?, block_ms?)` | Read inbox → `list[Message]` |

### Tools

| Method | Description |
|--------|-------------|
| `client.list_tools()` | List available built-in tools |
| `client.call_tool(tool_id, capability, parameters)` | Execute a tool → `ToolResult` |

### Pub/Sub

| Method | Description |
|--------|-------------|
| `client.list_topics()` | List active topics |
| `client.publish(topic, data)` | Publish to a topic |

## Error Handling

```python
from fabric_a2a_sdk import (
    FabricClient,
    FabricError,
    FabricConnectionError,
    FabricAuthError,
    FabricNotFoundError,
    FabricTimeoutError,
)

client = FabricClient("https://fabric.perceptor.us", "my-key")

try:
    result = client.call_agent("nonexistent-agent", "reason", "Hello")
except FabricNotFoundError:
    print("Agent not found — check the agent ID")
except FabricAuthError:
    print("Invalid API key")
except FabricTimeoutError:
    print("Agent took too long to respond")
except FabricConnectionError:
    print("Cannot reach the Fabric server")
except FabricError as e:
    print(f"Unexpected error: {e} (HTTP {e.status_code})")
```

## Message Priorities

```python
from fabric_a2a_sdk import FabricClient, MessagePriority

client.send_message(
    from_agent="alert-system",
    to_agent="ops-agent",
    payload={"alert": "CPU > 95%", "host": "gpu-node-01"},
    priority=MessagePriority.CRITICAL,
)
```

## CLI Usage

```bash
# Quick health check
fabric-a2a --url https://fabric.perceptor.us --key your-key ping

# List agents
fabric-a2a --url https://fabric.perceptor.us --key your-key agents

# List tools
fabric-a2a --url https://fabric.perceptor.us --key your-key tools
```

## Architecture

```
Your Agent ──→ FabricClient ──→ Fabric A2A Gateway ──→ Target Agent
                    │                    │
                    │              ┌─────┴──────┐
                    │              │ Redis       │
                    │              │ Streams     │
                    │              │ + Pub/Sub   │
                    │              └─────────────┘
                    │
                    └── HTTP/JSON ──→ /mcp/call
                                     /mcp/register_agent
                                     /mcp/list_agents
                                     /mcp/list_tools
                                     /mcp/health
```

## Requirements

- Python 3.10+
- No required dependencies (uses stdlib `urllib`)
- Optional: `httpx` for better performance

## License

MIT — Built by [AetherPro Technologies LLC](https://aetherpro.tech)

## Links

- **Dashboard**: [mcpfabric.space](https://mcpfabric.space)
- **API Docs**: [fabric.perceptor.us/mcp/docs](https://fabric.perceptor.us/mcp/docs)
- **Observatory**: [mcpfabric.space/observatory](https://mcpfabric.space/observatory)

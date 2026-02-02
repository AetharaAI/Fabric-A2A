# Fabric A2A Python SDK

A production-ready Python SDK for interacting with the Fabric Agent-to-Agent (A2A) protocol server.

## What is Fabric A2A?

Fabric A2A is an enterprise-grade agent-to-agent communication protocol that enables:

- **Agent Discovery** - Find and connect with AI agents by capability, trust tier, or tags
- **Built-in Tools** - Access file I/O, web requests, calculations, and more
- **Distributed Tracing** - Full observability with trace IDs across all calls
- **Async Support** - High-performance async/await patterns for concurrent operations

## Installation

### From PyPI (when published)

```bash
pip install fabric-a2a
```

### From Source

```bash
cd sdk/python
pip install .
```

### Development Install

```bash
cd sdk/python
pip install -e ".[dev]"
```

## Quickstart

```python
from fabric_a2a import FabricClient

# Initialize client
client = FabricClient(
    base_url="https://fabric.perceptor.us",
    token="your-api-token"
)

# Call a built-in tool
result = client.tools.math.calculate("2 + 2")
print(result)  # 4.0

# Check server health
health = client.health()
print(f"Server status: {health.status}")

client.close()
```

## Calling Agents

```python
from fabric_a2a import FabricClient, FabricError

client = FabricClient(
    base_url="https://fabric.perceptor.us",
    token="your-api-token"
)

try:
    # Simple call - returns just the answer string
    answer = client.agents.call_simple(
        agent_id="percy",
        capability="reason",
        task="Explain Python decorators in 2 sentences"
    )
    print(answer)

    # Detailed call with full control
    result = client.agents.call(
        agent_id="percy",
        capability="reason",
        task="What is 2+2?",
        timeout_ms=30000
    )
    
    if result.ok:
        print(f"Answer: {result.result.get('answer')}")
        print(f"Latency: {result.metrics.latency_ms}ms")
        print(f"Trace ID: {result.trace.trace_id}")

except FabricError as e:
    print(f"Error: {e.message}")
    print(f"Trace ID: {e.trace_id}")

client.close()
```

## Async Usage

```python
import asyncio
from fabric_a2a import AsyncFabricClient

async def main():
    async with AsyncFabricClient(
        base_url="https://fabric.perceptor.us",
        token="your-api-token"
    ) as client:
        # Make concurrent calls
        results = await asyncio.gather(
            client.tools.math.calculate("sqrt(144)"),
            client.agents.call_simple("percy", "reason", "Hello!"),
            client.health()
        )
        print(results)

asyncio.run(main())
```

## Agent Discovery

```python
# List all available agents
agents = client.agents.list()
for agent in agents:
    print(f"{agent.agent_id}: {agent.display_name}")
    print(f"  Status: {agent.status}")
    print(f"  Capabilities: {[c.name for c in agent.capabilities]}")
    print(f"  Trust Tier: {agent.trust_tier}")

# Find agents by capability
reasoning_agents = client.agents.find_by_capability("reason")

# Check if an agent is available
if client.agents.is_available("percy"):
    print("Percy is online!")
```

## Built-in Tools

```python
# File operations
content = client.tools.io.read_file("./README.md")
client.tools.io.write_file("./output.txt", "Hello, World!")

# Web requests
response = client.tools.web.get("https://api.example.com/data")
print(response.body)

# Math
calc = client.tools.math.calculate("sqrt(144) * 2")
stats = client.tools.math.statistics([1, 2, 3, 4, 5])

# Text processing
matches = client.tools.text.regex_match("Hello World", r"\w+")
diff = client.tools.text.diff("original", "modified")

# Security
hash_result = client.tools.security.hash("data", algorithm="sha256")
encoded = client.tools.security.base64_encode("hello")
```

## Error Handling

```python
from fabric_a2a import (
    FabricClient,
    FabricError,
    AgentNotFoundError,
    CapabilityNotFoundError,
    TimeoutError,
    AuthenticationError
)

client = FabricClient(...)

try:
    result = client.agents.call("unknown-agent", "reason", "test")
except AgentNotFoundError as e:
    print(f"Agent not found: {e.agent_id}")
except CapabilityNotFoundError as e:
    print(f"Capability not found: {e.capability}")
except TimeoutError as e:
    print(f"Call timed out after {e.timeout}s")
except AuthenticationError:
    print("Invalid or expired token")
except FabricError as e:
    print(f"Error [{e.code}]: {e.message}")
    print(f"Trace ID: {e.trace_id}")
```

## Context Manager

```python
# Automatically closes connection when done
with FabricClient(base_url=url, token=token) as client:
    result = client.tools.math.calculate("2 + 2")
    print(result)
# Connection closed automatically
```

## Registry (Enterprise)

For enterprise deployments with a registry:

```python
# List all registered agents
agents = client.registry.list_agents()

# Search by name or capability
results = client.registry.search("reasoning")

# Get agent details
agent = client.registry.get_agent("percy")
```

See the [main project documentation](../../README.md) for more details on the registry concept.

## Project Layout

```
sdk/python/
├── pyproject.toml          # Package configuration
├── README.md               # This file
├── fabric_a2a/             # Main package
│   ├── __init__.py         # Public API exports
│   ├── client.py           # FabricClient, AsyncFabricClient
│   ├── agents.py           # AgentClient for agent operations
│   ├── tools.py            # ToolClient for built-in tools
│   ├── models.py           # Pydantic data models
│   └── exceptions.py       # Custom exceptions
└── examples/
    └── quickstart.py       # Usage examples
```

## Requirements

- Python >= 3.10
- requests >= 2.28.0
- pydantic >= 2.0.0
- httpx >= 0.24.0 (for async support)

## License

MIT License - See [LICENSE](../../LICENSE) for details.

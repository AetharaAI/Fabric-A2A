# Fabric A2A Python SDK

Production-ready Python SDK for Fabric Agent-to-Agent (A2A) communication protocol.

## Features

- **Synchronous & Async clients** - Works in any Python application
- **Tool calls** - Access 20+ built-in tools
- **Agent communication** - Call other agents via MCP
- **Async messaging** - Redis Streams for persistent task queues
- **Pub/Sub** - Real-time event broadcasting
- **Streaming** - SSE support for streaming responses
- **Type safety** - Full Pydantic model support

## Installation

```bash
pip install fabric-a2a
```

Or from source:

```bash
cd fabric/sdk/python
pip install -e .
```

## Quick Start

### Synchronous Client

```python
from fabric_a2a import FabricClient

# Initialize
client = FabricClient(
    base_url="https://fabric.perceptor.us",
    token="your-auth-token"
)

# List available tools
tools = client.tools.list()
print(f"Found {len(tools)} tools")

# Call a tool
result = client.tools.math.calculate("2 + 2")
print(f"Result: {result}")

# List agents
agents = client.agents.list()
print(f"Found {len(agents)} agents")

# Call an agent
response = client.agents.call(
    agent_id="percy",
    capability="reason",
    task="What is machine learning?"
)
print(response.result)

client.close()
```

### Async Client

```python
import asyncio
from fabric_a2a import AsyncFabricClient

async def main():
    async with AsyncFabricClient(
        base_url="https://fabric.perceptor.us",
        token="your-auth-token"
    ) as client:
        # Concurrent calls
        results = await asyncio.gather(
            client.tools.math.calculate("sqrt(144)"),
            client.tools.math.calculate("10 * 10"),
            client.agents.list()
        )
        print(results)

asyncio.run(main())
```

## Async Messaging with Redis

For agent-to-agent async communication:

```python
from fabric_a2a import MessagingClient

async def messaging_example():
    # Create messaging client for your agent
    client = MessagingClient(
        agent_id="my-agent",
        redis_url="redis://localhost:6379",
        password="redis-password"
    )
    await client.connect()

    # Send task to another agent
    result = await client.send_task(
        to_agent="percy",
        task_type="reason",
        payload={"task": "Analyze this data"}
    )
    print(f"Sent: {result['message_id']}")

    # Receive messages from your inbox
    messages = await client.receive_messages(count=5, block_ms=5000)
    for msg in messages:
        print(f"From {msg.from_agent}: {msg.payload}")

    # Publish to a topic
    await client.publish("shared:insights", {"data": {...}})

    # Subscribe to topics
    async def handle_event(channel, data):
        print(f"Event on {channel}: {data}")

    await client.subscribe("shared:*", handle_event)

    await client.close()
```

### Message Handlers

```python
from fabric_a2a import MessagingClient

client = MessagingClient(agent_id="my-agent", redis_url="redis://redis://localhost:6379")

@client.on("task")
async def handle_task(msg):
    print(f"Got task: {msg.payload}")
    # Process task...
    await client.send_task(
        to_agent=msg.from_agent,
        task_type="result",
        payload={"result": "Done!"}
    })

# Start listening
await client.start_listening(block_ms=1000)
```

## Streaming Responses

For agents that support streaming:

```python
from fabric_a2a import FabricClient, StreamingResult

client = FabricClient(base_url="https://fabric.perceptor.us", token="token")

result = StreamingResult()

# Call with streaming
await client.call(
    "fabric.call",
    {
        "agent_id": "percy",
        "capability": "reason",
        "task": "Write a long story...",
        "stream": True
    },
    # Handle events via callback or iterator
)

# Or use SSE streaming directly
from fabric_a2a import stream_sSE

async def on_token(text):
    print(text, end="", flush=True)

await stream_sse(
    url="https://fabric.perceptor.us/mcp/call",
    headers={"Authorization": "Bearer token"},
    payload={"name": "fabric.call", "arguments": {...}},
    on_token=on_token
)
```

## Error Handling

```python
from fabric_a2a import FabricClient, FabricError, AgentNotFoundError

client = FabricClient(base_url="https://fabric.perceptor.us", token="token")

try:
    result = client.agents.call("unknown-agent", "reason", "test")
except AgentNotFoundError as e:
    print(f"Agent not found: {e.agent_id}")
except FabricError as e:
    print(f"Error {e.code}: {e.message}")
    print(f"Trace: {e.trace_id}")
```

## Configuration

### Environment Variables

```bash
export FABRIC_URL="https://fabric.perceptor.us"
export FABRIC_TOKEN="your-token"
```

### Pydantic Models

```python
from fabric_a2a import AgentInfo, ToolInfo, CallResult, TraceContext

# Access structured data
agent = client.agents.get("percy")
print(agent.display_name)
print(agent.capabilities)
print(agent.status)

# Trace context for debugging
result = client.tools.math.calculate("2 + 2")
print(result.trace.trace_id)
print(result.trace.span_id)
```

## WebSocket Support

```python
from fabric_a2a import WebSocketClient

async def ws_example():
    ws = WebSocketClient(
        url="ws://fabric.example.com/ws",
        token="your-token"
    )
    await ws.connect()

    # Send a call
    await ws.send_call(
        agent_id="percy",
        capability="reason",
        task="Hello!"
    )

    # Receive responses
    async for msg in ws.messages():
        print(msg)

    await ws.close()
```

## Examples

See `examples/quickstart.py` for complete examples:

```bash
python examples/quickstart.py
```

## Requirements

- Python 3.10+
- requests
- pydantic
- httpx
- redis (for messaging)

## License

MIT

# Fabric MCP Server - Universal Tool Server & Agent Gateway

A production-grade MCP server that serves as both a **Universal Tool Server** and an **Agent-to-Agent Communication Gateway**. Fabric provides 20+ built-in tools plus the ability to route calls between agents, all using the Model Context Protocol (MCP) as the interface.

## Overview

**Fabric** is two things in one:

1. **Universal Tool Server** - 20+ built-in tools for common operations (file I/O, HTTP requests, math, text processing, etc.) that any MCP client can use
2. **Agent Gateway** - Route calls between AI agents using MCP's tool-calling semantics

Instead of every agent framework reinventing the wheel, Fabric provides a shared tool inventory that all agents can access, plus seamless agent-to-agent communication.

### Key Philosophy
**"Communication is a tool. Agents are tools. Tools are capabilities. MCP is the interface."**

### Key Features

#### Universal Tool Server
- **20+ Built-in Tools**: File I/O, HTTP requests, math, text processing, system commands, data parsing
- **8 Tool Categories**: `io.*`, `web.*`, `math.*`, `text.*`, `system.*`, `data.*`, `security.*`, `encoding.*`
- **Tool Discovery**: `fabric.tool.list` to discover all available tools
- **Direct Tool Calls**: `fabric.tool.io.read_file`, `fabric.tool.math.calculate`, etc.
- **Secure by Default**: File access restrictions, command validation, sensitive data filtering

#### Agent Gateway
- **MCP-Native Interface**: Standard MCP tools for agent operations
- **Protocol Agnostic**: Runtime adapters support different agent protocols (MCP, Agent Zero, ACP, etc.)
- **Streaming Support**: Real-time token and event streaming via SSE
- **Authentication**: PSK and Passport-based auth with signature verification
- **Distributed Tracing**: Every call has trace_id and span_id for observability
- **Fail Loudly**: Structured errors with detailed context
- **Pluggable Registry**: YAML → PostgreSQL → Distributed (future)
- **Health Monitoring**: Automatic agent health checks and fallback routing

## Architecture

```
                          ┌─────────────────────────────────────┐
                          │         MCP Client Layer            │
                          └──────────────┬──────────────────────┘
                                         │
              ┌──────────────────────────▼──────────────────────────┐
              │              Fabric MCP Server                       │
              │  ┌──────────────────┬──────────────────────┐       │
              │  │  Built-in Tools  │   Agent Gateway      │       │
              │  │  ├ io.*          │   ├ fabric.call      │       │
              │  │  ├ web.*         │   ├ fabric.agent.*   │       │
              │  │  ├ math.*        │   └ Runtime Adapters │       │
              │  │  ├ text.*        │                      │       │
              │  │  ├ system.*      │                      │       │
              │  │  ├ data.*        │                      │       │
              │  │  └ security.*    │                      │       │
              │  └──────────────────┴──────────────────────┘       │
              │                      │                             │
              │              Agent Registry                        │
              │         ├ Built-in Tools Config                    │
              │         └ Remote Agent Config                      │
              └──────────────────────┬─────────────────────────────┘
                                     │
              ┌──────────────────────┴──────────────────────┐
              │         External Agent Runtimes             │
              │     (Percy, Coder, Vision, Memory, etc.)    │
              └─────────────────────────────────────────────┘
```

See [architecture.md](architecture.md) for detailed diagrams and data flows.

## Universal Tool Inventory

Fabric includes **20+ built-in tools** that any MCP client can use immediately:

### Tool Categories

| Category | Tools | Example Usage |
|----------|-------|---------------|
| **io** | File read, write, list, search | `fabric.tool.io.read_file` |
| **web** | HTTP requests, page fetch, URL parse | `fabric.tool.web.http_request` |
| **math** | Calculator, statistics | `fabric.tool.math.calculate` |
| **text** | Regex, transform, diff | `fabric.tool.text.regex` |
| **system** | Execute commands, env vars, datetime | `fabric.tool.system.execute` |
| **data** | JSON parse, CSV parse, validate | `fabric.tool.data.json` |
| **security** | Hash, base64 | `fabric.tool.security.hash` |
| **encoding** | URL encode/decode | `fabric.tool.encode.url` |
| **docs** | Markdown processing | `fabric.tool.docs.markdown` |

### Using Built-in Tools

```bash
# List all available tools
curl -H "Authorization: Bearer dev-shared-secret" \
  -X POST http://localhost:8000/mcp/call \
  -d '{"name": "fabric.tool.list", "arguments": {}}'

# Calculate expression
curl -H "Authorization: Bearer dev-shared-secret" \
  -X POST http://localhost:8000/mcp/call \
  -d '{
    "name": "fabric.tool.math.calculate",
    "arguments": {"expression": "sqrt(144) * 2"}
  }'

# Read a file
curl -H "Authorization: Bearer dev-shared-secret" \
  -X POST http://localhost:8000/mcp/call \
  -d '{
    "name": "fabric.tool.io.read_file",
    "arguments": {"path": "./README.md"}
  }'

# Generate SHA256 hash
curl -H "Authorization: Bearer dev-shared-secret" \
  -X POST http://localhost:8000/mcp/call \
  -d '{
    "name": "fabric.tool.security.hash",
    "arguments": {"data": "Hello, World!", "algorithm": "sha256"}
  }'

# Make HTTP request
curl -H "Authorization: Bearer dev-shared-secret" \
  -X POST http://localhost:8000/mcp/call \
  -d '{
    "name": "fabric.tool.web.http_request",
    "arguments": {"url": "https://api.github.com/users/octocat"}
  }'
```

See [TOOLS_INVENTORY.md](TOOLS_INVENTORY.md) for complete documentation of all built-in tools.

## Installation

### Prerequisites

- Python 3.11+
- pip or uv package manager

### Setup

```bash
# Clone or navigate to the project directory
cd a2a-mcp

# Install dependencies
pip install -r requirements.txt

# Or using uv (faster)
uv pip install -r requirements.txt
```

## Configuration

### Agent Registry (agents.yaml)

Define your agents in `agents.yaml`:

```yaml
agents:
  - agent_id: percy
    display_name: Percy
    version: 1.2.0
    description: General reasoning and planning agent
    runtime: mcp  # or 'agentzero', 'acp', etc.
    endpoint:
      transport: http
      uri: http://localhost:8001/mcp
    capabilities:
      - name: reason
        description: General reasoning and analysis
        streaming: true
        modalities: [text]
        input_schema:
          type: object
          properties:
            task: { type: string }
          required: [task]
        output_schema:
          type: object
          properties:
            answer: { type: string }
        max_timeout_ms: 120000
    tags: [planner, reasoning]
    trust_tier: org
```

See the included `agents.yaml` for complete examples.

## Usage

### Running the Server

#### STDIO Transport (for local MCP clients)

```bash
python server.py --transport stdio --config agents.yaml
```

Use this mode when integrating with MCP clients like Claude Desktop or local agent frameworks.

#### HTTP Transport (for remote access)

```bash
python server.py --transport http --port 8000 --config agents.yaml --psk your-secret-key
```

The server will be available at `http://localhost:8000`.

### MCP Tools

The Fabric server exposes the following MCP tools:

#### Built-in Tool Tools

#### 1. `fabric.tool.list`

List all available tools (built-in + agents).

**Input:**
```json
{
  "category": "math",
  "provider": "builtin"
}
```

**Output:**
```json
{
  "tools": [
    {"tool_id": "math.calculate", "provider": "builtin", "category": "math"},
    {"tool_id": "math.statistics", "provider": "builtin", "category": "math"}
  ],
  "count": 2
}
```

#### 2. `fabric.tool.call`

Execute a built-in tool.

**Input:**
```json
{
  "tool_id": "io.read_file",
  "capability": "read",
  "parameters": {"path": "./file.txt"}
}
```

#### 3. `fabric.tool.describe`

Get detailed information about a tool.

**Input:**
```json
{
  "tool_id": "io.read_file"
}
```

#### Direct Tool Calls

You can also call tools directly:
```json
{
  "name": "fabric.tool.math.calculate",
  "arguments": {"expression": "2 + 2"}
}
```

---

#### Agent Communication Tools

#### 4. `fabric.agent.list`

List all registered agents with optional filters.

**Input:**
```json
{
  "filter": {
    "capability": "reason",
    "tag": "planner",
    "status": "online"
  }
}
```

**Output:**
```json
{
  "agents": [
    {
      "agent_id": "percy",
      "display_name": "Percy",
      "version": "1.2.0",
      "status": "online",
      "capabilities": [...],
      "tags": ["planner", "reasoning"],
      "trust_tier": "org"
    }
  ]
}
```

#### 2. `fabric.agent.describe`

Get detailed information about a specific agent.

**Input:**
```json
{
  "agent_id": "percy"
}
```

**Output:**
```json
{
  "agent": {
    "agent_id": "percy",
    "capabilities": [
      {
        "name": "reason",
        "description": "General reasoning and analysis",
        "input_schema": {...},
        "output_schema": {...},
        "streaming": true,
        "max_timeout_ms": 120000
      }
    ]
  }
}
```

#### 3. `fabric.call`

Call an agent's capability (the main A2A communication tool).

**Input (Synchronous):**
```json
{
  "agent_id": "percy",
  "capability": "reason",
  "task": "Analyze the pros and cons of microservices architecture",
  "context": {
    "domain": "software architecture",
    "depth": "detailed"
  },
  "stream": false,
  "timeout_ms": 60000
}
```

**Output:**
```json
{
  "ok": true,
  "trace": {
    "trace_id": "550e8400-e29b-41d4-a716-446655440000",
    "span_id": "7f3a8b2c-1d9e-4f5a-b3c2-9e8d7c6b5a4f"
  },
  "result": {
    "answer": "...",
    "reasoning_steps": [...],
    "citations": [...]
  }
}
```

**Input (Streaming):**
```json
{
  "agent_id": "coder",
  "capability": "code",
  "task": "Write a Python function to calculate Fibonacci numbers",
  "stream": true
}
```

**Output (SSE stream):**
```
data: {"event":"status","data":{"status":"running","trace":{...}}}

data: {"event":"token","data":{"text":"def fibonacci(n):","trace":{...}}}

data: {"event":"token","data":{"text":"\n    if n <= 1:","trace":{...}}}

data: {"event":"final","data":{"ok":true,"result":{...},"trace":{...}}}
```

#### 4. `fabric.route.preview`

Preview where a call would be routed (for debugging).

**Input:**
```json
{
  "agent_id": "percy",
  "capability": "reason"
}
```

**Output:**
```json
{
  "selected_runtime": {
    "transport": "http",
    "uri": "http://localhost:8001/mcp",
    "adapter": "RuntimeMCP"
  },
  "policy": {
    "allowed": true,
    "reason": "ok"
  },
  "fallbacks": [
    {
      "agent_id": "percy-backup",
      "reason": "Same capability: reason",
      "priority": 1
    }
  ]
}
```

#### 5. `fabric.health`

Check system health.

**Output:**
```json
{
  "ok": true,
  "registry": "ok",
  "runtimes": {
    "online": 4,
    "offline": 1,
    "degraded": 0
  },
  "version": "af-mcp-0.1",
  "uptime_seconds": 3600
}
```

### Error Handling

All errors follow a consistent structure:

```json
{
  "ok": false,
  "error": {
    "code": "AGENT_OFFLINE",
    "message": "Agent percy is offline",
    "details": {
      "agent_id": "percy",
      "last_seen": "2026-01-24T10:30:00Z"
    }
  },
  "trace": {
    "trace_id": "...",
    "span_id": "..."
  }
}
```

**Error Codes:**
- `AGENT_OFFLINE`: Agent is not responding
- `AGENT_NOT_FOUND`: Agent ID not in registry
- `CAPABILITY_NOT_FOUND`: Agent doesn't have requested capability
- `AUTH_DENIED`: Authentication failed
- `AUTH_EXPIRED`: Auth token expired
- `AUTH_INVALID`: Invalid auth credentials
- `TIMEOUT`: Call exceeded timeout
- `BAD_INPUT`: Invalid request parameters
- `UPSTREAM_ERROR`: Error from agent runtime
- `INTERNAL_ERROR`: Server internal error
- `RATE_LIMITED`: Too many requests

## Authentication

### Pre-Shared Key (PSK)

For development and simple deployments:

```bash
# Start server with PSK
python server.py --transport http --psk my-secret-key

# Client includes in Authorization header
curl -H "Authorization: Bearer my-secret-key" \
  -X POST http://localhost:8000/mcp/call \
  -d '{"name":"fabric.agent.list","arguments":{}}'
```

### Agent Passport (Future)

For production deployments with cryptographic verification:

```json
{
  "passport": {
    "principal_id": "user:alice",
    "agent_passport_id": "agent:percy#cert-123",
    "delegation": ["capability:reason", "capability:plan"],
    "expires_at": "2026-01-25T00:00:00Z",
    "signature": "base64-encoded-ed25519-signature",
    "key_id": "kid:xyz"
  }
}
```

The server will verify:
- Ed25519 signature using registered public key
- Expiration timestamp
- Delegation scope (allowed capabilities)
- Trust tier rules

## Runtime Adapters

Fabric uses runtime adapters to communicate with different agent protocols.

### Built-in Adapters

#### RuntimeMCP
For agents that speak native MCP protocol.

```python
adapter = RuntimeMCP(agent_id, endpoint, manifest)
```

#### RuntimeAgentZero
For agents using Agent Zero RFC/FastA2A protocol.

```python
adapter = RuntimeAgentZero(agent_id, endpoint, manifest)
```

### Creating Custom Adapters

Implement the `RuntimeAdapter` interface:

```python
class RuntimeAdapter:
    async def call(self, envelope: CanonicalEnvelope) -> Dict[str, Any]:
        """Execute synchronous call"""
        raise NotImplementedError
    
    async def call_stream(self, envelope: CanonicalEnvelope) -> AsyncIterator[Dict[str, Any]]:
        """Execute streaming call"""
        raise NotImplementedError
    
    async def health(self) -> AgentStatus:
        """Check agent health"""
        raise NotImplementedError
    
    async def describe(self) -> AgentManifest:
        """Get agent manifest"""
        raise NotImplementedError
```

Example custom adapter:

```python
class RuntimeCustomProtocol(RuntimeAdapter):
    def __init__(self, agent_id: str, endpoint: AgentEndpoint, manifest: AgentManifest):
        self.agent_id = agent_id
        self.endpoint = endpoint
        self.manifest = manifest
        self.client = CustomProtocolClient(endpoint.uri)
    
    async def call(self, envelope: CanonicalEnvelope) -> Dict[str, Any]:
        # Translate envelope to custom protocol
        request = {
            "agent": envelope.target["agent_id"],
            "action": envelope.target["capability"],
            "payload": envelope.input["task"]
        }
        
        # Make call
        response = await self.client.execute(request)
        
        # Translate response back to Fabric format
        return {
            "ok": True,
            "trace": envelope.trace.to_dict(),
            "result": response
        }
    
    async def health(self) -> AgentStatus:
        try:
            await self.client.ping()
            return AgentStatus.ONLINE
        except:
            return AgentStatus.OFFLINE
```

## Observability

### Structured Logging

All logs are JSON-formatted with trace context:

```json
{
  "timestamp": "2026-01-24T10:30:00Z",
  "level": "INFO",
  "message": "Executing call: percy.reason",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "span_id": "7f3a8b2c-1d9e-4f5a-b3c2-9e8d7c6b5a4f"
}
```

### Distributed Tracing

Every call generates a trace context:

```python
trace = TraceContext.create(
    trace_id="550e8400-e29b-41d4-a716-446655440000",  # Optional: continue existing trace
    parent_span_id="parent-span-id"  # Optional: link to parent
)
```

Integrate with Jaeger, Tempo, or other tracing backends by exporting trace IDs.

### Metrics

Key metrics to monitor:

- **Call latency**: Time from request to response
- **Error rate**: Errors per error code
- **Agent availability**: Online/offline/degraded counts
- **Throughput**: Calls per second per agent
- **Streaming events**: Events per second for streaming calls

## Testing

### Manual Testing with curl

```bash
# List agents
curl -H "Authorization: Bearer dev-shared-secret" \
  -X POST http://localhost:8000/mcp/call \
  -d '{
    "name": "fabric.agent.list",
    "arguments": {}
  }'

# Call an agent
curl -H "Authorization: Bearer dev-shared-secret" \
  -X POST http://localhost:8000/mcp/call \
  -d '{
    "name": "fabric.call",
    "arguments": {
      "agent_id": "percy",
      "capability": "reason",
      "task": "What is the meaning of life?"
    }
  }'

# Streaming call
curl -H "Authorization: Bearer dev-shared-secret" \
  -X POST http://localhost:8000/mcp/call \
  -d '{
    "name": "fabric.call",
    "arguments": {
      "agent_id": "percy",
      "capability": "reason",
      "task": "Explain quantum computing",
      "stream": true
    }
  }'
```

### Python Client Example

```python
import requests

FABRIC_URL = "http://localhost:8000/mcp/call"
AUTH_TOKEN = "dev-shared-secret"

def call_agent(agent_id: str, capability: str, task: str):
    response = requests.post(
        FABRIC_URL,
        headers={"Authorization": f"Bearer {AUTH_TOKEN}"},
        json={
            "name": "fabric.call",
            "arguments": {
                "agent_id": agent_id,
                "capability": capability,
                "task": task
            }
        }
    )
    return response.json()

# Use it
result = call_agent("percy", "reason", "Analyze the benefits of Rust")
print(result["result"]["answer"])
```

## Deployment

### Development (Single Node)

```bash
python server.py --transport stdio --config agents.yaml
```

### Production (Multi-Node)

1. **Deploy Fabric Gateway**:
   ```bash
   # Use HTTP transport with proper auth
   python server.py \
     --transport http \
     --port 8000 \
     --config agents.yaml \
     --psk $FABRIC_PSK
   ```

2. **Deploy Agent Runtimes** on separate nodes/containers

3. **Configure Load Balancer** in front of Fabric gateway

4. **Set up Observability**:
   - Export logs to Loki/CloudWatch
   - Export traces to Jaeger/Tempo
   - Export metrics to Prometheus

5. **Database Registry** (future):
   - Migrate from YAML to PostgreSQL
   - Enable dynamic agent registration
   - Support distributed registry with consensus

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .
COPY agents.yaml .

EXPOSE 8000

CMD ["python", "server.py", "--transport", "http", "--port", "8000"]
```

```bash
docker build -t fabric-mcp-server .
docker run -p 8000:8000 -e FABRIC_PSK=secret fabric-mcp-server
```

## Roadmap

### v0.1 (Current)
- ✅ Core MCP tools (list, describe, call, health, route.preview)
- ✅ **Universal Tool Inventory** - 20+ built-in tools
- ✅ **Tool Categories** - io, web, math, text, system, data, security, encoding, docs
- ✅ PSK authentication
- ✅ YAML registry
- ✅ RuntimeMCP and RuntimeAgentZero adapters
- ✅ Streaming support (SSE)
- ✅ Distributed tracing

### v0.2 (Next)
- [ ] Agent Passport authentication with Ed25519
- [ ] **More built-in tools** - Database, cache, image, PDF, Git, Docker
- [ ] Async job handles (fabric.job.*)
- [ ] PostgreSQL registry backend
- [ ] WebSocket transport
- [ ] Metrics export (Prometheus)
- [ ] Fallback routing with health checks
- [ ] Tool composition pipelines

### v1.0 (Future)
- [ ] Distributed registry with consensus
- [ ] Multi-region support
- [ ] Rate limiting and quotas
- [ ] Agent capability negotiation
- [ ] Federation with other Fabric instances
- [ ] Web UI for monitoring and debugging

## Contributing

This is a reference implementation. To extend:

1. **Add Runtime Adapters**: Implement `RuntimeAdapter` for new protocols
2. **Registry Backends**: Swap YAML for PostgreSQL, Redis, etc.
3. **Auth Methods**: Add OAuth, mTLS, or custom auth
4. **Transports**: Add gRPC, MQTT, or other transports
5. **Observability**: Integrate with your monitoring stack

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or contributions:
- GitHub Issues: [your-repo/issues]
- Documentation: [architecture.md](architecture.md), [schemas.json](schemas.json)
- Specification: [Agent_to_Agent_MCP_Server.md](Agent_to_Agent_MCP_Server.md)

---

**Built with the philosophy**: Communication is a tool. Agents are tools. Tools are capabilities. MCP is the interface.

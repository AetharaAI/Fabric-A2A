# Fabric MCP Server - Project Summary

## Overview

The **Fabric MCP Server** is a production-grade Agent-to-Agent (A2A) communication gateway that uses the Model Context Protocol (MCP) as its interface. Rather than inventing a new protocol for agent communication, Fabric leverages MCP's existing tool-calling semantics to expose agents as callable tools. This approach provides a universal, standardized way for agents to discover and communicate with each other.

## Core Concept

**Communication is a tool. Agents are tools. MCP is the interface.**

Instead of creating yet another agent communication protocol, Fabric treats agent capabilities as MCP tools. Any MCP-compatible client can discover agents, inspect their capabilities, and invoke them through standard MCP tool calls. The Fabric server acts as a gateway that handles routing, authentication, streaming, and observability.

## Architecture Highlights

### Components

1. **Fabric MCP Server (Gateway)**: The central hub that exposes MCP tools for agent operations
2. **Agent Registry**: Discovers and tracks available agents and their capabilities
3. **Runtime Adapters**: Protocol translators that allow agents using different protocols (MCP, Agent Zero, ACP, etc.) to communicate through the gateway
4. **Authentication Layer**: PSK and Passport-based authentication with cryptographic verification
5. **Observability Layer**: Distributed tracing, structured logging, and metrics

### Data Flow

```
MCP Client → fabric.call → Fabric Gateway → Runtime Adapter → Agent Runtime
                                ↓
                          Registry Lookup
                                ↓
                          Auth Verification
                                ↓
                          Trace Generation
                                ↓
                          Response (sync or stream)
```

## Key Features

### 1. MCP-Native Interface
All agent operations are exposed through standard MCP tools:
- `fabric.agent.list` - Discover agents
- `fabric.agent.describe` - Get agent details
- `fabric.call` - Invoke agent capabilities
- `fabric.route.preview` - Debug routing
- `fabric.health` - System health check

### 2. Protocol Agnostic
Runtime adapters enable communication with agents using different protocols:
- **RuntimeMCP**: Native MCP agents
- **RuntimeAgentZero**: Agent Zero RFC/FastA2A protocol
- **RuntimeACP**: Agent Communication Protocol
- **Custom adapters**: Easy to implement for any protocol

### 3. Streaming Support
Real-time streaming via Server-Sent Events (SSE):
- Token-by-token text streaming
- Progress updates
- Tool call events
- Final results

### 4. Authentication & Security
- **PSK (Pre-Shared Key)**: Simple authentication for development
- **Agent Passport**: Cryptographic verification with Ed25519 signatures (future)
- **Trust Tiers**: Local, org, and public trust levels
- **Delegation Scopes**: Fine-grained capability permissions

### 5. Observability
- **Distributed Tracing**: Every call has trace_id and span_id
- **Structured Logging**: JSON logs with trace context
- **Health Monitoring**: Automatic agent health checks
- **Metrics**: Latency, errors, throughput

### 6. Fail Loudly
Structured errors with detailed context:
- Machine-readable error codes
- Human-readable messages
- Trace context for debugging
- Detailed error information

## File Structure

```
a2a-mcp/
├── server.py                 # Main server implementation (800+ lines)
├── agents.yaml              # Agent registry configuration
├── schemas.json             # Complete MCP tool schemas
├── requirements.txt         # Python dependencies
├── README.md                # Comprehensive documentation
├── QUICKSTART.md            # 5-minute getting started guide
├── architecture.md          # Detailed architecture diagrams
├── integration_guide.md     # Agent developer integration guide
├── example_client.py        # Example Python client
├── Dockerfile               # Container image definition
├── docker-compose.yml       # Multi-container orchestration
├── .env.example             # Environment variable template
├── .gitignore               # Git ignore rules
└── LICENSE                  # MIT License
```

## Implementation Details

### Server Implementation (server.py)

The server is implemented in Python using FastAPI and includes:

- **Data Models**: Comprehensive dataclasses for all entities (TraceContext, AuthContext, AgentManifest, CanonicalEnvelope, etc.)
- **Runtime Adapter Interface**: Abstract base class with concrete implementations for MCP and Agent Zero
- **Agent Registry**: In-memory registry with support for filtering, health checks, and fallback resolution
- **Authentication Service**: PSK verification with hooks for future Passport implementation
- **Fabric Server**: Main request handler with routing logic
- **Transport Layers**: Both stdio and HTTP transports
- **Streaming Support**: SSE-based streaming for real-time responses
- **Error Handling**: Comprehensive error codes and structured error responses

### Agent Registry (agents.yaml)

Example agents included:
- **Percy**: Reasoning and planning agent
- **Coder**: Code generation and review
- **Vision**: Image analysis and generation
- **Memory**: Long-term memory storage and retrieval
- **Orchestrator**: Multi-agent coordination

Each agent entry includes:
- Unique identifier and metadata
- Endpoint configuration (transport and URI)
- Capability definitions with schemas
- Tags for discovery
- Trust tier classification

### MCP Tool Schemas (schemas.json)

Complete JSON Schema definitions for:
- All 5 MCP tools with input/output schemas
- Streaming event formats
- Error response structure
- Canonical envelope format

## Usage Examples

### Starting the Server

```bash
# STDIO transport (for local MCP clients)
python server.py --transport stdio --config agents.yaml

# HTTP transport (for remote access)
python server.py --transport http --port 8000 --config agents.yaml --psk your-secret
```

### Calling an Agent

```python
import requests

response = requests.post(
    "http://localhost:8000/mcp/call",
    headers={"Authorization": "Bearer dev-shared-secret"},
    json={
        "name": "fabric.call",
        "arguments": {
            "agent_id": "percy",
            "capability": "reason",
            "task": "Analyze the benefits of microservices"
        }
    }
)

result = response.json()
print(result["result"]["answer"])
```

### Streaming Response

```python
response = requests.post(
    "http://localhost:8000/mcp/call",
    headers={"Authorization": "Bearer dev-shared-secret"},
    json={
        "name": "fabric.call",
        "arguments": {
            "agent_id": "coder",
            "capability": "code",
            "task": "Write a Python web scraper",
            "stream": True
        }
    },
    stream=True
)

for line in response.iter_lines():
    if line.startswith(b"data: "):
        event = json.loads(line[6:])
        print(event)
```

## Integration Guide

For agent developers, integration involves:

1. **Create Agent Manifest**: Add entry to `agents.yaml` with agent metadata and capabilities
2. **Implement Agent Runtime**: Expose capabilities via HTTP endpoint (MCP or custom protocol)
3. **Optional: Create Custom Adapter**: If using a non-MCP protocol, implement a RuntimeAdapter subclass

The integration guide provides:
- Detailed manifest structure and examples
- Native MCP agent implementation guide
- Custom adapter creation instructions
- Streaming implementation guide
- Best practices for agent development

## Deployment Options

### Development
```bash
python server.py --transport stdio
```

### Production (Docker)
```bash
docker-compose up -d
```

### Production (Kubernetes)
Deploy as a standard HTTP service with:
- Horizontal pod autoscaling
- Health check endpoints
- ConfigMap for agents.yaml
- Secrets for authentication

## Future Roadmap

### v0.2 (Next Release)
- Agent Passport authentication with Ed25519
- Async job handles (fabric.job.*)
- PostgreSQL registry backend
- WebSocket transport
- Metrics export (Prometheus)

### v1.0 (Future)
- Distributed registry with consensus
- Multi-region support
- Rate limiting and quotas
- Agent capability negotiation
- Federation with other Fabric instances
- Web UI for monitoring

## Design Principles

1. **Use MCP, Don't Invent**: Leverage existing MCP semantics rather than creating new protocols
2. **Agents as Tools**: Treat agent capabilities as callable tools
3. **Protocol Agnostic**: Support any agent protocol through adapters
4. **Fail Loudly**: Provide clear, structured errors with full context
5. **Observable by Default**: Every call is traced, logged, and measurable
6. **Extensible**: Registry and adapters are pluggable
7. **Secure**: Authentication at gateway with optional agent re-verification
8. **Streaming First**: Support real-time token and event streaming

## Technical Specifications

- **Language**: Python 3.11+
- **Framework**: FastAPI + Uvicorn
- **Transport**: stdio, HTTP, WebSocket (future)
- **Authentication**: PSK, Passport (future), mTLS (future)
- **Serialization**: JSON
- **Streaming**: Server-Sent Events (SSE)
- **Tracing**: UUID-based trace_id and span_id
- **Logging**: Structured JSON logs

## Dependencies

Core:
- fastapi (0.109.0)
- uvicorn (0.27.0)
- pydantic (2.5.3)
- pyyaml (6.0.1)

Future:
- cryptography (42.0.0) - for Passport auth
- pynacl (1.5.0) - for Ed25519 signatures
- psycopg2-binary (2.9.9) - for PostgreSQL registry
- sqlalchemy (2.0.25) - for ORM

## Testing

The project includes:
- **example_client.py**: Comprehensive test client demonstrating all MCP tools
- **Mock adapters**: RuntimeMCP and RuntimeAgentZero with mock responses for testing
- **Health checks**: Built-in health endpoint for monitoring

## Documentation

Complete documentation set:
- **README.md**: Full usage guide (200+ lines)
- **QUICKSTART.md**: 5-minute getting started
- **architecture.md**: Detailed system design with ASCII diagrams
- **integration_guide.md**: Agent developer guide
- **schemas.json**: Complete MCP tool schemas
- **PROJECT_SUMMARY.md**: This document

## Conclusion

The Fabric MCP Server provides a production-ready, extensible foundation for agent-to-agent communication. By leveraging MCP as the interface rather than inventing a new protocol, it enables immediate integration with the growing ecosystem of MCP-compatible tools and agents. The pluggable runtime adapter architecture ensures compatibility with any agent protocol, while the comprehensive observability features make it suitable for production deployments.

The implementation demonstrates that **communication is indeed a tool**, and MCP provides the perfect abstraction layer for that tool.

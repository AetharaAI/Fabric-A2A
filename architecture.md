# Agent-to-Agent MCP Server Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MCP Client Layer                             │
│  (Any MCP-compatible client: Claude Desktop, custom agents, etc.)   │
└────────────────────────────┬────────────────────────────────────────┘
                             │ MCP Protocol (stdio/HTTP/WebSocket)
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                    Fabric MCP Server (Gateway)                       │
│                                                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  MCP Tool Interface                                           │  │
│  │  • fabric.agent.list      • fabric.call                       │  │
│  │  • fabric.agent.describe  • fabric.route.preview              │  │
│  │  • fabric.health          • [fabric.job.* - future]           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                             │                                         │
│  ┌──────────────────────────▼────────────────────────────────────┐  │
│  │  Request Pipeline                                              │  │
│  │  1. Schema Validation                                          │  │
│  │  2. Authentication (PSK/Passport/mTLS)                         │  │
│  │  3. Trace ID Generation                                        │  │
│  │  4. Envelope Construction                                      │  │
│  └──────────────────────────┬────────────────────────────────────┘  │
│                             │                                         │
│  ┌──────────────────────────▼────────────────────────────────────┐  │
│  │  Agent Registry                                                │  │
│  │  • Agent discovery and lookup                                  │  │
│  │  • Capability matching                                         │  │
│  │  • Health status tracking                                      │  │
│  │  • Fallback resolution                                         │  │
│  │  Sources: YAML config → PostgreSQL → Distributed (future)     │  │
│  └──────────────────────────┬────────────────────────────────────┘  │
│                             │                                         │
│  ┌──────────────────────────▼────────────────────────────────────┐  │
│  │  Runtime Adapter Layer                                         │  │
│  │  • RuntimeMCP         (native MCP agents)                      │  │
│  │  • RuntimeAgentZero   (Agent Zero RFC/FastA2A)                 │  │
│  │  • RuntimeACP         (Agent Communication Protocol)           │  │
│  │  • RuntimeLocalProcess (spawned processes)                     │  │
│  │  • RuntimeHTTP        (generic HTTP/REST)                      │  │
│  └──────────────────────────┬────────────────────────────────────┘  │
│                             │                                         │
│  ┌──────────────────────────▼────────────────────────────────────┐  │
│  │  Response Handler                                              │  │
│  │  • Streaming (SSE/WebSocket)                                   │  │
│  │  • Synchronous responses                                       │  │
│  │  • Async job handles (future)                                  │  │
│  │  • Error normalization                                         │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Observability Layer                                           │  │
│  │  • Structured logging (JSON)                                   │  │
│  │  • Distributed tracing (trace_id, span_id)                     │  │
│  │  • Metrics (latency, errors, agent availability)               │  │
│  └────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │ Adapter-specific protocols
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                      Agent Runtime Layer                             │
│                                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │
│  │   Agent A   │  │   Agent B   │  │   Agent C   │  │  Agent D  │  │
│  │   (MCP)     │  │ (AgentZero) │  │   (ACP)     │  │  (Local)  │  │
│  │             │  │             │  │             │  │           │  │
│  │ Capability: │  │ Capability: │  │ Capability: │  │Capability:│  │
│  │ • reason    │  │ • code      │  │ • vision    │  │ • tools   │  │
│  │ • planning  │  │ • execution │  │ • image_gen │  │ • memory  │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow: fabric.call Execution

```
1. Client Request
   │
   ├─→ MCP Tool Call: fabric.call
   │   {
   │     "agent_id": "percy",
   │     "capability": "reason",
   │     "task": "Analyze this data",
   │     "stream": true
   │   }
   │
2. Fabric Gateway
   │
   ├─→ Validate Schema ✓
   │
   ├─→ Authenticate
   │   • Verify PSK/Passport
   │   • Check delegation scope
   │
   ├─→ Generate Trace Context
   │   trace_id: "550e8400-e29b-41d4-a716-446655440000"
   │   span_id: "7f3a8b2c-1d9e-4f5a-b3c2-9e8d7c6b5a4f"
   │
   ├─→ Registry Lookup
   │   • Find agent "percy"
   │   • Verify capability "reason"
   │   • Get endpoint: http://node-1.internal/agents/percy
   │   • Check health status: online
   │
   ├─→ Build Canonical Envelope
   │   {
   │     "trace": { "trace_id": "...", "span_id": "..." },
   │     "auth": { "mode": "psk", "principal_id": "client-123" },
   │     "target": { "agent_id": "percy", "capability": "reason" },
   │     "input": { "task": "Analyze this data", ... },
   │     "response": { "stream": true, "format": "text" }
   │   }
   │
   ├─→ Select Runtime Adapter
   │   RuntimeMCP (percy speaks native MCP)
   │
3. Runtime Adapter
   │
   ├─→ RuntimeMCP.call(envelope)
   │   • Translate envelope → MCP tool call
   │   • Open streaming connection
   │   • Forward to agent endpoint
   │
4. Agent Execution
   │
   ├─→ Agent "percy" processes task
   │   • Streams tokens back
   │   • Emits progress events
   │   • Returns final result
   │
5. Response Streaming
   │
   ├─→ Adapter streams events back to Fabric
   │   event: token  → { "text": "Analyzing..." }
   │   event: progress → { "percent": 50 }
   │   event: token  → { "text": "Complete." }
   │   event: final  → { "answer": "...", "citations": [...] }
   │
   ├─→ Fabric forwards to client via MCP streaming
   │
6. Client Receives
   │
   └─→ Streaming MCP response with trace context
```

## Authentication Flow

```
┌─────────────┐                 ┌──────────────┐                ┌──────────┐
│  MCP Client │                 │    Fabric    │                │  Agent   │
└──────┬──────┘                 └──────┬───────┘                └────┬─────┘
       │                               │                             │
       │ 1. MCP call + auth header     │                             │
       ├──────────────────────────────►│                             │
       │   Authorization: Bearer <psk> │                             │
       │   OR                           │                             │
       │   X-Agent-Passport: {...}      │                             │
       │                               │                             │
       │                               │ 2. Verify auth              │
       │                               │    • PSK match              │
       │                               │    • Passport signature     │
       │                               │    • Expiry check           │
       │                               │    • Delegation scope       │
       │                               │                             │
       │                               │ 3. Stamp auth context       │
       │                               │    in envelope              │
       │                               │                             │
       │                               │ 4. Forward with auth        │
       │                               ├────────────────────────────►│
       │                               │    (agent can re-verify)    │
       │                               │                             │
       │                               │ 5. Response                 │
       │                               │◄────────────────────────────┤
       │                               │                             │
       │ 6. Return to client           │                             │
       │◄──────────────────────────────┤                             │
       │   with trace_id               │                             │
       │                               │                             │
```

## Registry Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                      Registry Interface                         │
│  • list_agents(filter)                                          │
│  • get_agent(agent_id)                                          │
│  • register_agent(manifest)                                     │
│  • update_health(agent_id, status)                              │
│  • find_by_capability(capability)                               │
└──────────────────────┬─────────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
┌───────▼──────┐ ┌─────▼──────┐ ┌────▼─────────┐
│ YAML Config  │ │ PostgreSQL │ │ Distributed  │
│  (v0.1)      │ │  (v0.2)    │ │  (v1.0)      │
│              │ │            │ │              │
│ agents.yaml  │ │ agents tbl │ │ Registrar    │
│ • Simple     │ │ • Indexed  │ │ • Consensus  │
│ • Fast       │ │ • ACID     │ │ • Multi-node │
│ • Git-able   │ │ • Queries  │ │ • Federated  │
└──────────────┘ └────────────┘ └──────────────┘
```

## Error Handling and Fallbacks

```
fabric.call(agent_id="percy", capability="reason", task="...")
    │
    ├─→ Primary: Agent "percy" @ node-1
    │   │
    │   ├─→ Success ✓ → Return result
    │   │
    │   ├─→ Timeout ✗
    │   │   └─→ Try fallback
    │   │
    │   ├─→ Agent offline ✗
    │   │   └─→ Try fallback
    │   │
    │   └─→ Capability error ✗
    │       └─→ Try fallback
    │
    └─→ Fallback: Agent "percy-backup" @ node-2
        │
        ├─→ Success ✓ → Return result (with fallback metadata)
        │
        └─→ All fallbacks exhausted ✗
            └─→ Return structured error:
                {
                  "ok": false,
                  "error": {
                    "code": "AGENT_OFFLINE",
                    "message": "Agent percy unavailable and all fallbacks failed",
                    "details": {
                      "primary": "percy@node-1: timeout",
                      "fallbacks": ["percy-backup@node-2: offline"]
                    }
                  },
                  "trace": { "trace_id": "...", "span_id": "..." }
                }
```

## Deployment Topology Examples

### Single-Node Development
```
┌─────────────────────────────┐
│  localhost                   │
│  ┌─────────────────────────┐│
│  │  Fabric MCP Server      ││
│  │  (stdio transport)      ││
│  └───────┬─────────────────┘│
│          │                  │
│  ┌───────▼─────────────────┐│
│  │  Local Agent Processes  ││
│  │  • percy (port 8001)    ││
│  │  • coder (port 8002)    ││
│  └─────────────────────────┘│
└─────────────────────────────┘
```

### Multi-Node Production
```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│  Gateway     │         │   Node 1     │         │   Node 2     │
│              │         │              │         │              │
│  Fabric MCP  │◄───────►│  Agent A     │         │  Agent C     │
│  Server      │         │  Agent B     │         │  Agent D     │
│  (HTTP/WS)   │         │              │         │              │
│              │         │              │         │              │
│  Registry    │◄───────►│  Runtime     │◄───────►│  Runtime     │
│  (Postgres)  │         │  Adapters    │         │  Adapters    │
└──────────────┘         └──────────────┘         └──────────────┘
       │
       │
┌──────▼──────────────────────────────────────────────────────────┐
│  Observability Stack                                             │
│  • Logs → Loki/CloudWatch                                        │
│  • Traces → Jaeger/Tempo                                         │
│  • Metrics → Prometheus/Grafana                                  │
└──────────────────────────────────────────────────────────────────┘
```

## Key Design Principles

1. **MCP is the Interface**: Everything exposed through standard MCP tools
2. **Agents are Tools**: Each agent capability appears as a callable tool
3. **Protocol Agnostic**: Runtime adapters handle different agent protocols
4. **Fail Loudly**: Structured errors with trace context
5. **Observable**: Every call has trace_id, structured logs, metrics
6. **Extensible**: Registry and adapters are pluggable
7. **Secure**: Auth at gateway, optional re-verification at agents
8. **Streaming First**: Support for real-time token/event streaming

---

## Appendix: Aether Fabric MCP Profile (AF-MCP) v0.1

This appendix merges the standalone AF-MCP specification into the canonical architecture reference so that the complete protocol surface and runtime expectations live in a single source.

### Purpose

- Present agents as MCP tools discoverable via a consistent registry contract.
- Enable routing across local and remote runtimes with unified streaming behavior.
- Support PSK authentication today, with Passport/mTLS hooks for zero-trust deployments.
- Maintain observability and graceful failure semantics for every agent call.

### Canonical Concepts

**Agent Identity**

- `agent_id`, `node_id`, `version`, `capabilities`
- Capabilities track modality, streaming support, and timeout hints.

**Canonical Envelope**

auth.delegate_id (sub)

auth.principal_id (prn)

auth.mandate_id (mnd)

auth.cog_id (cog)

auth.cap and auth.scp derived from the minted Mandate token

```json
{
  "trace": {"trace_id": "uuid", "span_id": "uuid", "parent_span_id": "uuid|null"},
  "auth": {
    "mode": "psk|passport|mtls|none",
    "principal_id": "string|null",
    "agent_passport_id": "string|null",
    "signature": "string|null",
    "key_id": "string|null"
  },
  "target": {"agent_id": "string", "capability": "string", "timeout_ms": 60000},
  "input": {"task": "string", "context": {}, "attachments": []},
  "response": {"stream": true, "format": "text|json|toolcalls"}
}
```

All inbound MCP calls are normalized into this envelope before hitting runtime adapters.

### MCP Tool Surface

| Tool | Description |
| --- | --- |
| `fabric.agent.list` | Enumerates agents with capability manifests and trust tiers. |
| `fabric.agent.describe` | Returns a single agent's schema-rich manifest. |
| `fabric.call` | Primary execution lane with sync, streaming, and async job handles. |
| `fabric.route.preview` | Debug utility for routing decisions and fallback visibility. |
| `fabric.health` | Gateway and registry health snapshot. |

Streaming responses emit `status`, `token`, `tool_call`, `progress`, and `final` events with full trace context.

### Auth + Passport Hooks

- **PSK Baseline**: `Authorization: Bearer <psk>` header mapped to `auth.mode="psk"`.
- **Passport Ready**: Structured passport metadata (`principal_id`, delegation scopes, expiry, signature, `key_id`). Verification happens at the Fabric gateway, with optional downstream checks.

### Async Jobs & Timeouts

- Long-running capabilities may return `job_id` handles with follow-up tools (`fabric.job.status`, `fabric.job.stream`, `fabric.job.cancel`) earmarked for v0.2.
- Timeouts are enforced at the adapter boundary, triggering fallback policy when exceeded.

### Failure Modes

Canonical error payload:

```json
{
  "ok": false,
  "error": {
    "code": "AGENT_OFFLINE|AUTH_DENIED|CAPABILITY_NOT_FOUND|TIMEOUT|BAD_INPUT|UPSTREAM_ERROR",
    "message": "human readable",
    "details": {"agent_id": "...", "capability": "...", "upstream": "..."}
  },
  "trace": {"trace_id": "...", "span_id": "..."}
}
```

Fallback tiers include same-capability peers, degraded modes (e.g., downgrade to non-streaming), or policy-driven refusals for untrusted origins.

### Registry Model

- **v0.1**: YAML (`agents.yaml`) checked into the repo.
- **v0.2**: Postgres-backed registry with health telemetry.
- **v1.0**: Distributed registrar mesh with consensus and federation rules.

Minimum manifest example:

```yaml
- agent_id: percy
  endpoint:
    transport: http
    uri: https://node-1.internal/agents/percy
  capabilities:
    - name: reason
      streaming: true
      modalities: [text]
  trust_tier: org
  tags: [planner, dev]
```

### Runtime Adapters

Each adapter implements:

```python
class RuntimeAdapter:
    async def call(envelope) -> result_or_stream
    async def health() -> status
    async def describe() -> manifest
```

Stock adapters: `RuntimeMCP`, `RuntimeAgentZeroRFC`, `RuntimeACP`, `RuntimeLocalProcess`, `RuntimeHTTP`.

### Reference Loop & Observability

1. Receive MCP request.
2. Validate schema + auth; stamp trace context.
3. Resolve registry entry and select runtime adapter.
4. Execute call, streaming events back as they arrive.
5. Emit structured logs, traces, and metrics per call.

Observability requirements include trace IDs on every log line, structured JSON logging, and Prometheus-friendly metrics for latency, errors, and agent availability.

### v0.1 Shipping Checklist

- Implement `fabric.agent.list`, `fabric.agent.describe`, `fabric.call` (with streaming), PSK auth, YAML registry, and at least one runtime adapter.
- Optional: Add `fabric.route.preview` and `fabric.health` for richer operator ergonomics.

This appendix captures the AF-MCP intent verbatim, ensuring downstream consumers only need this file for both system architecture and detailed protocol semantics.

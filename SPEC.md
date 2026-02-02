# Fabric A2A MCP Protocol Specification
Version: 0.1.0
Status: Draft
Author: Fabric Community

---

## 1. Overview

Fabric is an Agent-to-Agent (A2A) communication protocol built on top of MCP (Model Context Protocol). It allows autonomous agents to expose capabilities as callable endpoints and interact over a standardized tool-call interface.

Fabric nodes act as MCP servers that:

- register agents
- expose tools
- execute calls
- return structured traceable responses

This specification defines the wire format and behavior required for interoperability.

---

## 2. Transport

Fabric runs over HTTP(S).

Default endpoint:

POST /mcp/call
GET  /health

All Fabric messages are JSON.

Authentication is implementation-defined. Reference node uses Bearer token auth.

---

## 3. Request Format

A Fabric request MUST be a JSON object:

{
  "name": "fabric.call",
  "arguments": { ... }
}

### 3.1 Tool Call Request

{
  "name": "fabric.tool.<tool_name>",
  "arguments": { ... }
}

### 3.2 Agent Call Request

{
  "name": "fabric.call",
  "arguments": {
    "agent_id": "<agent_name>",
    "capability": "<capability>",
    "task": "<instruction>"
  }
}

---

## 4. Response Format

All Fabric responses MUST follow:

{
  "ok": true,
  "trace": {
    "trace_id": "<uuid>",
    "span_id": "<uuid>",
    "parent_span_id": null
  },
  "result": { ... },
  "error": null
}

On failure:

{
  "ok": false,
  "trace": { ... },
  "result": null,
  "error": "<message>"
}

Trace IDs MUST be unique per call.

---

## 5. Agent Registration

Agents are registered at startup.

Each agent exposes:

- agent_id
- capability list
- execution handler

Nodes MAY dynamically load agents.

---

## 6. Tool Registry

Tools are globally namespaced:

fabric.tool.<category>.<name>

Examples:

fabric.tool.math.calculate
fabric.tool.io.read_file
fabric.tool.agent.percy.reason

Tools MUST be deterministic and side-effect safe unless explicitly declared otherwise.

---

## 7. Trace Semantics

Fabric includes distributed tracing.

Each request generates:

- trace_id (global call)
- span_id (local execution)
- parent_span_id (optional)

Trace metadata MUST propagate across agent boundaries.

---

## 8. Health Endpoint

GET /health

Response:

{
  "status": "ok",
  "version": "af-mcp-0.1"
}

Nodes MUST expose a health endpoint.

---

## 9. Interoperability Rules

A Fabric-compatible node MUST:

- implement /mcp/call
- return valid trace objects
- follow request/response schema
- expose health endpoint
- use JSON encoding

Any node following this spec is considered Fabric-compatible.

---

## 10. Future Extensions

Reserved areas:

- streaming responses
- agent discovery
- mesh routing
- cryptographic identity
- Passport integration
- signed trace envelopes

These extensions MUST remain backward compatible.

---

End of Specification

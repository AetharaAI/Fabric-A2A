
````
# Fabric A2A Protocol Specification v0.1

## Overview

Fabric A2A defines a lightweight JSON RPC-style protocol for agent-to-agent and tool execution over HTTP.

The protocol is transport-agnostic but currently specified over HTTPS.

This document defines the wire contract. SDKs are adapters. The spec is authoritative.

---

## Endpoint

POST /mcp/call

Content-Type: application/json

---

## Request Format

```json
{
  "name": "string",
  "arguments": { "object": "any" }
}
````

### Fields

* `name`
  Fully-qualified call target. Examples:

  * `fabric.tool.math.calculate`
  * `fabric.call`

* `arguments`
  Arbitrary JSON payload passed to the tool or agent.

---

## Response Format

```json
{
  "ok": true,
  "trace": {
    "trace_id": "uuid",
    "span_id": "uuid",
    "parent_span_id": null
  },
  "result": { "any": "json" },
  "error": null
}
```

### Fields

* `ok`
  Boolean success flag

* `trace`
  Execution metadata

* `result`
  Tool or agent output

* `error`
  Structured error object or null

---

## Trace Semantics

Each request MUST generate a unique `trace_id`.

* `trace_id` — request lifetime identifier
* `span_id` — execution unit
* `parent_span_id` — optional for nested calls

Trace data is transport metadata. Clients MUST NOT depend on specific formats beyond UUID semantics.

---

## Tool Namespace

```
fabric.tool.*
```

Reserved for built-in and community tools.

Example:

```
fabric.tool.math.calculate
fabric.tool.clock
```

---

## Agent Namespace

```
fabric.call
```

Agent dispatch request:

```json
{
  "name": "fabric.call",
  "arguments": {
    "agent_id": "string",
    "capability": "string",
    "task": "string"
  }
}
```

---

## Errors

Errors MUST return:

```json
{
  "ok": false,
  "error": {
    "type": "string",
    "message": "string"
  }
}
```

No exception text should leak server internals.

---

## Versioning

Protocol version is implicit in server implementation.

Future versions MUST remain backward compatible within minor revisions.

Breaking changes require:

```
v1.0 spec freeze
```

---

## Registry (Reserved)

Agent and tool registries are external discovery layers.

They are NOT part of the execution protocol.

This separation is intentional.

```

---

That file is your constitution.

SDKs can evolve.
Servers can evolve.
Your spec is the stable surface other people build against.

Once SPEC.md exists, you’re not “hacking a project”.

You’re stewarding a protocol.

---

## Now: contribution guardrails

Create:

```

CONTRIBUTING.md

```

Paste:

```

# Contributing to Fabric A2A

Fabric A2A is a protocol-first project.

Changes to behavior must update SPEC.md.

## Rules

1. Fork → branch → PR
2. Formatting: black .
3. No breaking protocol changes without spec revision
4. Add examples for new tools or agents
5. Keep SDKs thin; protocol logic lives in the server

Design discussion happens in issues before implementation.

```

This prevents chaos later.

Future you will thank current you.

---

## Release tag

From repo root:

```

git tag v0.1.0
git push origin v0.1.0

```

That tag is history. Immutable checkpoint. You can always say:

> Fabric A2A v0.1 started here.

Protocols grow in layers. This is layer one.

---


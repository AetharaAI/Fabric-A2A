# HARNESS_INTEGRATION_OPERATING_GUIDE.md

## Purpose
This document is the current operator guide for integrating external agent harnesses with the live Fabric-A2A backend running on this VM.

It is written for real harness repos that need to:
- hold a scoped Fabric API key in their own `.env`
- verify connectivity and auth on startup
- send and receive A2A work over Fabric
- use Fabric tools when needed
- stay aligned with the live MCPFabric dashboard and backend contract

This guide reflects the live production state as of `2026-03-20`.

## Canonical Endpoints
- Backend base URL: `https://fabric.perceptor.us`
- Frontend operator UI: `https://mcpfabric.space`

Primary endpoints:
- `GET /admin/verify`
- `POST /mcp/call`
- `GET /mcp/list_agents`
- `GET /mcp/list_tools`
- `GET /mcp/list_topics`
- `GET /mcp/agent/{agent_id}`

## Current Auth Model
Fabric currently uses:
- one admin master key for platform administration
- scoped `fab_sk_live_*` API keys for harnesses, agents, gateways, and operators

Recommended pattern:
- do not place the admin key in agent harness repos
- create one live scoped key per harness or per fleet role
- store that scoped key in the harness `.env`

## Minimum Harness Environment Contract
Each harness repo should define at least:

```bash
FABRIC_BASE_URL=https://fabric.perceptor.us
FABRIC_API_KEY=fab_sk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
FABRIC_AGENT_ID=your-agent-id
```

Recommended additions:

```bash
FABRIC_FROM_AGENT=your-agent-id
FABRIC_DEFAULT_TARGET=percy
FABRIC_REQUEST_TIMEOUT=30
FABRIC_VERIFY_ON_START=true
```

## Boot Sequence For A Harness
On harness startup:
1. load `.env`
2. verify the scoped key with `/admin/verify`
3. confirm the returned `owner_id` and `scope`
4. optionally call `/mcp/list_tools` or `/mcp/list_agents` once for sanity
5. begin normal send/receive work

If `/admin/verify` fails:
- stop the harness boot
- log the HTTP status and body
- do not silently continue

## Required Request Format
`/mcp/call` currently accepts plain MCP-style payloads like:

```json
{
  "name": "fabric.message.send",
  "arguments": {
    "to_agent": "percy",
    "from_agent": "orchestrator",
    "message_type": "task",
    "payload": {
      "task_type": "health_check"
    }
  }
}
```

Do not wrap these calls in JSON-RPC unless the backend is explicitly changed to require it.

## Proved Working Operations
These flows are already verified on this VM:
- admin verify
- scoped client key verify
- standard tool call via `/mcp/call`
- `fabric.message.send`
- `fabric.message.queue_status`

Treat these as the stable baseline for harness integration.

## Curl Smoke Tests For Harness Owners

### 1. Verify the harness key
```bash
curl -sS "$FABRIC_BASE_URL/admin/verify" \
  -H "Authorization: Bearer $FABRIC_API_KEY"
```

Expected success shape:
```json
{
  "ok": true,
  "method": "api_key",
  "scope": "full",
  "owner_id": "your-owner-id"
}
```

### 2. Prove tool-call path
```bash
curl -sS -X POST "$FABRIC_BASE_URL/mcp/call" \
  -H "Authorization: Bearer $FABRIC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "fabric.tool.math.calculate",
    "arguments": {
      "expression": "2 + 2"
    }
  }'
```

### 3. Send A2A work
```bash
curl -sS -X POST "$FABRIC_BASE_URL/mcp/call" \
  -H "Authorization: Bearer $FABRIC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "fabric.message.send",
    "arguments": {
      "to_agent": "percy",
      "from_agent": "orchestrator",
      "message_type": "task",
      "payload": {
        "task_type": "health_check",
        "note": "harness smoke test"
      },
      "priority": "normal"
    }
  }'
```

Expected success shape:
```json
{
  "message_id": "msg:...",
  "status": "queued",
  "stream_id": "...."
}
```

### 4. Check target queue
```bash
curl -sS -X POST "$FABRIC_BASE_URL/mcp/call" \
  -H "Authorization: Bearer $FABRIC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "fabric.message.queue_status",
    "arguments": {
      "agent_id": "percy"
    }
  }'
```

## Python Harness Reference

```python
import os
import requests

BASE_URL = os.environ["FABRIC_BASE_URL"].rstrip("/")
API_KEY = os.environ["FABRIC_API_KEY"]
AGENT_ID = os.environ["FABRIC_AGENT_ID"]

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


def fabric_verify():
    response = requests.get(f"{BASE_URL}/admin/verify", headers=HEADERS, timeout=15)
    response.raise_for_status()
    return response.json()


def fabric_call(name: str, arguments: dict):
    response = requests.post(
        f"{BASE_URL}/mcp/call",
        headers=HEADERS,
        json={"name": name, "arguments": arguments},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def send_task(to_agent: str, payload: dict, message_type: str = "task"):
    return fabric_call(
        "fabric.message.send",
        {
            "to_agent": to_agent,
            "from_agent": AGENT_ID,
            "message_type": message_type,
            "payload": payload,
            "priority": "normal",
        },
    )


def queue_status(agent_id: str):
    return fabric_call("fabric.message.queue_status", {"agent_id": agent_id})
```

## Recommended Harness Adapter Shape
Each harness should isolate Fabric in one adapter module, for example:

```text
fabric_client.py
  - verify()
  - call(name, arguments)
  - send_message(to_agent, payload, message_type="task")
  - queue_status(agent_id)
  - list_agents()
  - list_tools()
```

Do not scatter raw `requests.post("/mcp/call")` logic all over the harness codebase.

## Suggested Harness Semantics

### For sender/orchestrator harnesses
Use:
- `fabric.message.send` for work delegation
- `fabric.message.queue_status` to confirm the target queue is moving
- tool calls for shared utilities only when the harness itself should not own the capability

### For worker harnesses
Use:
- a receive/poll loop if your harness is actively consuming queued work
- agent-specific logic outside Fabric for the actual task execution
- optional send-back or reply path after work completion

### For utility harnesses
Use:
- direct tool calls when they are mostly invoking Fabric’s built-in tooling
- A2A messages only when task routing or persistence matters

## Operating Notes
- A harness key should map to a clear owner identity.
- Keep one key per harness or role unless there is a strong reason to share.
- If a harness loses function, verify `/admin/verify` first.
- If curl works but a browser UI fails, suspect CORS first.
- If the queue depth grows but work is not being consumed, the problem is usually on the consumer side, not in key auth.

## UI Alignment
The MCPFabric UI now supports:
- creating scoped keys
- verifying keys
- running live tool and message calls

Relevant operator pages:
- `https://mcpfabric.space/api-keys`
- `https://mcpfabric.space/playground`

Use the UI for operator work, but keep harness repos independently functional from CLI and code.

## What To Hand Codex In A Harness Repo
When you want Codex to wire a harness, provide:
- the harness repo path
- the agent role and `FABRIC_AGENT_ID`
- whether it only sends, only receives, or does both
- the exact payloads or task envelope you want exchanged
- any retry/timeout/backoff expectations

That is enough to build the adapter and the first live smoke test.


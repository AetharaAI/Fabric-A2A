# AGENTS.md

## Role
This repository is the Fabric-A2A backend for MCPFabric.

Primary agent responsibility on this VM:
- own the backend contract and production behavior for Fabric
- preserve working auth, key issuance, tool calls, and A2A message flows
- support MCPFabric frontend integration without destabilizing production

This backend was originally coded and iterated by Codex. The frontend was created by Manus AI and is being converted to match this backend.

## Environment
- Backend repo root: `/home/ubuntu/fabric/mcp-modular/Fabric-A2A`
- Live backend URL: `https://fabric.perceptor.us`
- Frontend URL consuming this backend: `https://mcpfabric.space`

## Current Mission
Keep Fabric-A2A stable as the live source of truth for:
- admin authentication
- API key lifecycle
- MCP tool invocation
- A2A message bus operations
- queue inspection
- eventually browser-safe observability and streaming support

## Working Rules
- Do not change successful production behavior casually.
- When frontend issues appear, confirm whether they are:
  - contract mismatch
  - browser/CORS mismatch
  - UI-only defect
- Preserve the curl-smoke-tested behaviors before refactoring.
- Avoid backend edits until the frontend proves a real backend gap.
- Never weaken auth just to make the frontend easier.

## Known Production Facts
- admin verify works
- production key creation works
- client key verify works
- `/mcp/call` works for standard tool execution
- `/mcp/call` works for `fabric.message.send`
- `/mcp/call` works for `fabric.message.queue_status`
- browser CORS/preflight is now configured for `https://mcpfabric.space`

## Backend Contract Notes
- `/admin/verify` is the primary auth verification endpoint
- `/admin/keys` supports create/list/revoke
- `/mcp/call` currently accepts plain payloads like:
  - `{ "name": "fabric.tool.math.calculate", "arguments": { ... } }`
  - `{ "name": "fabric.message.send", "arguments": { ... } }`
  - `{ "name": "fabric.message.queue_status", "arguments": { ... } }`

## Documentation Discipline
Keep these files updated when backend state changes materially:
- `AGENTS.md`
- `PROJECT_STATE.md`
- `CHANGELOG.md`

## Coordination Notes
- Frontend repo: `/home/ubuntu/mcp-fabric-site/MCPFabric`
- Browser issues that do not reproduce in curl are likely CORS/preflight first, then payload shape.
- Prefer minimal, explicit CORS allowances over broad permissive settings.

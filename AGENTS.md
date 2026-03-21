# AGENTS.md

## Role
This repository is the Fabric-A2A backend for MCPFabric.

Primary agent responsibility on this VM:
- own the backend contract and production behavior for Fabric
- preserve working auth, key issuance, MCP execution, and A2A message flows
- support the MCPFabric frontend without destabilizing production
- keep canonical project docs current whenever backend truth changes

This backend was originally coded and iterated by Codex. The MCPFabric frontend was originally created by Manus AI and is being aligned to this backend.

## Environment
- Backend repo root: `/home/ubuntu/fabric/mcp-modular/Fabric-A2A`
- Public API URL: `https://fabric.perceptor.us`
- Frontend URL consuming this backend: `https://mcpfabric.space`
- Frontend repo root: `/home/ubuntu/mcp-fabric-site/MCPFabric`
- GitHub repo: `git@github.com:AetharaAI/Fabric-A2A.git`

## Infra Truth
- Provider: OVHcloud Public Cloud
- Region: Oregon, US
- Instance type for this node: `b3-32`
- Tailscale mesh IP for this node: `100.126.206.81`
- Program: OVHcloud AI Accelerator Program
- Program tier: Scale tier as of early February 2026

## Current Mission
Keep Fabric-A2A stable as the live source of truth for:
- admin authentication
- API key lifecycle
- MCP tool invocation
- A2A message bus operations
- queue inspection
- frontend-safe browser integration
- future async observability and agent identity enhancements

## Working Rules
- Do not change successful production behavior casually.
- Confirm whether a frontend issue is a contract gap, browser/CORS issue, or UI defect before editing the backend.
- Preserve smoke-tested curl behaviors before refactoring.
- Never weaken auth to compensate for UI assumptions.
- Commit backend truth before doing branch merges.

## Canonical Docs
These files are canonical truth and must be updated when production state changes materially:
- `AGENTS.md`
- `PROJECT_STATE.md`
- `CHANGELOG.md`
- `TRUTH.md`

Template references for reuse across other systems live in:
- `TRUTH/README.md`
- `TRUTH/AGENTS.template.md`
- `TRUTH/PROJECT_STATE.template.md`
- `TRUTH/CHANGELOG.template.md`
- `TRUTH/TRUTH.template.md`

## Known Production Facts
- admin verify works
- production key creation works
- client key verify works
- `/mcp/call` works for standard tool execution
- `/mcp/call` works for `fabric.message.send`
- `/mcp/call` works for `fabric.message.queue_status`
- browser CORS/preflight is configured for `https://mcpfabric.space`
- the backend feature branch `mcp-modular` was merged into `main`
- both `main` and `mcp-modular` were pushed to origin

## Contract Notes
- `/admin/verify` is the primary auth verification endpoint
- `/admin/keys` supports create/list/revoke
- `/mcp/call` accepts plain payloads like `{ "name": "...", "arguments": { ... } }`
- browser preflight for protected endpoints must succeed before auth logic runs

## Standard Workflow
1. verify runtime behavior with curl or browser-safe checks
2. patch backend only when needed
3. update canonical docs
4. restart/rebuild only as required
5. verify live responses
6. commit and push from a clean branch/worktree

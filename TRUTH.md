# TRUTH.md

## Identity
- Project: Fabric-A2A
- Purpose: production Fabric backend, A2A platform, MCP execution layer, and SDK source
- Frontend consumer repo: `git@github.com:AetharaAI/MCPFabric.git`
- Backend repo: `git@github.com:AetharaAI/Fabric-A2A.git`

## Runtime
- Public API URL: `https://fabric.perceptor.us`
- Backend repo root: `/home/ubuntu/fabric/mcp-modular/Fabric-A2A`
- Frontend repo root: `/home/ubuntu/mcp-fabric-site/MCPFabric`
- external smoke test note: `/home/ubuntu/mcp-fabric-site/smoke-test.md`

## Infra
- Provider: OVHcloud Public Cloud
- Datacenter region: Oregon, US
- Instance type: `b3-32`
- Tailscale IP: `100.126.206.81`
- Program: OVHcloud AI Accelerator Program
- Program tier: Scale tier
- Credits: `$10k/month`, unused credits roll over
- Reported current burn: about `$7.5k/month`

## Current Production Truth
- backend auth and API key system are live and working
- MCP tool calls are live and working
- A2A message send and queue status flows are live and working
- browser CORS/preflight support for `mcpfabric.space` is live
- `mcp-modular` has been merged into `main`
- both `main` and `mcp-modular` were pushed to origin

## Operator Mechanics
- update `AGENTS.md`, `PROJECT_STATE.md`, `CHANGELOG.md`, and `TRUTH.md` whenever backend truth changes
- verify contract behavior with curl before changing frontend assumptions
- merge from clean worktrees when branch divergence is large

## Ownership
- Codex is the active engineering/operator agent for Fabric-A2A on this VM

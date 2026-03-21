# PROJECT_STATE.md

## Repo
- Name: Fabric-A2A backend
- Root: `/home/ubuntu/fabric/mcp-modular/Fabric-A2A`
- Public API URL: `https://fabric.perceptor.us`
- GitHub: `git@github.com:AetharaAI/Fabric-A2A.git`

## Production Status
Backend is live, working, and branch-aligned.

Verified working:
- admin auth verification
- admin API key creation
- scoped API key verification
- standard `/mcp/call` tool execution
- `fabric.message.send`
- `fabric.message.queue_status`
- browser-safe preflight for protected endpoints needed by MCPFabric

## Branch And Publish Status
- `mcp-modular` was the long-running feature branch carrying the platform expansion
- `mcp-modular` was merged into `main`
- merged `main` was pushed to `origin`
- updated `mcp-modular` was also pushed to `origin`

## Runtime Browser Integration Reality
- CORS/preflight was a real backend mismatch exposed by the frontend
- `OPTIONS` for `/admin/verify` and `/mcp/call` now return success
- authorized cross-origin responses now include `Access-Control-Allow-Origin: https://mcpfabric.space`
- MCPFabric browser operator flows can now talk to the backend across origins

## Smoke-Test Reference
- external note kept outside repos: `/home/ubuntu/mcp-fabric-site/smoke-test.md`

Important tested sequence:
1. verify admin key
2. create production gateway/client key
3. verify scoped client key
4. call a standard tool
5. call `fabric.message.send`
6. call `fabric.message.queue_status`

## Current Relationship To MCPFabric
- `/api-keys` and `/playground` in MCPFabric are aligned with backend behavior
- Console was converted away from mock activity to real operator-side interactions
- the remaining major frontend work is live observability and registry truth, not backend auth/key parity

## Remaining Backend Work
- formalize backend-side Passport identity binding for audits if required
- expose any missing async observability endpoints only when the frontend has a concrete data-plane shape
- keep SDK and platform docs trimmed and accurate as the platform stabilizes

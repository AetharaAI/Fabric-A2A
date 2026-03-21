# PROJECT_STATE.md

## Repo
- Name: Fabric-A2A backend
- Root: `/home/ubuntu/fabric/mcp-modular/Fabric-A2A`
- Public API URL: `https://fabric.perceptor.us`

## Current Status
Backend core production behaviors are working.

Verified working:
- admin auth verification
- admin API key creation
- scoped API key verification
- standard `/mcp/call` tool execution
- `fabric.message.send`
- `fabric.message.queue_status`

Current blocking issue for MCPFabric browser UI:
- CORS/preflight was blocking the browser and has now been fixed in the backend runtime
- browser-style `OPTIONS` for `/admin/verify` and `/mcp/call` now return `200 OK`
- authorized cross-origin success responses now include `Access-Control-Allow-Origin: https://mcpfabric.space`

## Smoke-Test Reference
External note maintained outside repos:
- `/home/ubuntu/mcp-fabric-site/smoke-test.md`

Important smoke-tested sequence:
1. verify admin key
2. create production gateway/client key
3. verify scoped client key
4. call `fabric.tool.math.calculate`
5. call `fabric.message.send`
6. call `fabric.message.queue_status`

## Current Integration Reality
- Frontend `/api-keys` and `/playground` were updated to align with backend behavior.
- Frontend deploy is live on `mcpfabric.space`.
- Primary remaining work is frontend-side live async/observability conversion.

## Next Recommended Backend Work
1. Validate browser flows from `mcpfabric.space` against the live backend.
2. Verify additional endpoints used next also return correct CORS behavior.
3. Help frontend wire real async streaming/observability if needed.

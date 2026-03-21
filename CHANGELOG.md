# CHANGELOG.md

## 2026-03-20

### Operational documentation
- Added backend-root `AGENTS.md`
- Added backend-root `PROJECT_STATE.md`
- Added backend-root `CHANGELOG.md`

### Integration state
- Recorded that production backend auth and A2A message flows are verified working.
- Recorded that MCPFabric browser failures were due to CORS/preflight, not key expiry.
- Recorded the external smoke-test note path used to validate the backend:
  - `/home/ubuntu/mcp-fabric-site/smoke-test.md`

### Backend runtime fix
- Added FastAPI CORS middleware in `server.py`.
- Allowed `OPTIONS` requests to pass through auth middleware in `auth.py`.
- Rebuilt and restarted `fabric-gateway`.
- Verified live preflight success for `/admin/verify` and `/mcp/call`.
- Verified authorized cross-origin success responses now carry `Access-Control-Allow-Origin: https://mcpfabric.space`.

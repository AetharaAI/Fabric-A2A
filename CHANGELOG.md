# CHANGELOG.md

## 2026-03-21

### Branch alignment
- committed the live backend delta on `mcp-modular`
- merged `mcp-modular` into `main`
- pushed `main` to origin
- pushed the updated `mcp-modular` branch to origin

### Browser integration
- preserved the backend CORS and `OPTIONS` handling required for MCPFabric browser use
- confirmed the backend remains the production source of truth for auth, key issuance, MCP calls, and A2A flows

### Documentation system
- elevated `AGENTS.md`, `PROJECT_STATE.md`, `CHANGELOG.md`, and `TRUTH.md` to canonical status
- added a reusable `TRUTH/` template system for standardized project documentation across production systems

## 2026-03-20

### Operational documentation
- added backend-root `AGENTS.md`
- added backend-root `PROJECT_STATE.md`
- added backend-root `CHANGELOG.md`

### Backend runtime fix
- added FastAPI CORS middleware in `server.py`
- allowed `OPTIONS` requests to pass through auth middleware in `auth.py`
- rebuilt and restarted `fabric-gateway`
- verified live preflight success for `/admin/verify` and `/mcp/call`
- verified authorized cross-origin success responses now carry `Access-Control-Allow-Origin: https://mcpfabric.space`

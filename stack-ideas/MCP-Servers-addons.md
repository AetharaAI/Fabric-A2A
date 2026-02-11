Based on what I see in your VS Code and the task ahead, here are the **essential MCP servers** to add for maximum effectiveness:

---

## Required MCP Servers for Passport IAM Implementation

### 1. **GitHub MCP** ✅ (Already installed)
**Use**: Repository management, code review, PR creation
**Why**: Kimi will need to commit the fork, manage branches, and potentially reference Keycloak's upstream code

---

### 2. **PostgreSQL MCP**
**Command**: `npx -y @modelcontextprotocol/server-postgres@latest`
**Arguments**: `--connection-string postgresql://passport:password@localhost:5432/passport`
**Use**: Database schema validation, migration testing, JPA entity verification
**Why**: Your Agency extensions need custom tables—Kimi needs to verify Liquibase migrations work

---

### 3. **Docker MCP**
**Command**: `npx -y @modelcontextprotocol/server-docker@latest`
**Use**: Container builds, image inspection, compose validation
**Why**: Critical for the final deployment phase—testing the Dockerfile and docker-compose setup

---

### 4. **Filesystem MCP** (Enhanced access)
**Command**: `npx -y @modelcontextprotocol/server-filesystem@latest`
**Arguments**: `/home/cory/passport-iam` (your project root)
**Use**: Full project navigation, file creation, batch operations
**Why**: Kimi needs unrestricted access to create the deep directory structure

---

### 5. **Web Fetch MCP**
**Command**: `npx -y @modelcontextprotocol/server-fetch@latest`
**Use**: Download Keycloak source references, PatternFly docs, verify API specs
**Why**: Cross-reference Keycloak's actual implementation vs. your requirements

---

### 6. **Playwright MCP** ✅ (Already installed—keep it)
**Use**: UI automation, visual regression testing
**Why**: Verify the "half-screen" fix actually works by screenshotting the running UI

---

## Recommended Configuration Order

| Priority | Server | When to Enable |
|----------|--------|----------------|
| 1 | Filesystem | Immediately—core development |
| 2 | GitHub | Immediately—version control |
| 3 | PostgreSQL | After database setup (Day 1-2) |
| 4 | Docker | During deployment phase (Day 4-5) |
| 5 | Web Fetch | As needed for reference |
| 6 | Playwright | For UI verification |

---

## Quick Add Commands

Copy-paste these into Kimi Code's MCP Server panel:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem@latest", "/home/cory/passport-iam"]
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres@latest", "--connection-string", "postgresql://passport:password@localhost:5432/passport"]
    },
    "docker": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-docker@latest"]
    },
    "fetch": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-fetch@latest"]
    }
  }
}
```

---

## Special: Custom "Passport" MCP (Optional but Powerful)

If you want **maximum integration**, create a custom MCP that connects to your existing services:

**File: `mcp-passport-server.js`**
```javascript
#!/usr/bin/env node
// Custom MCP for Passport ecosystem integration

const { Server } = require('@modelcontextprotocol/sdk/server/index.js');
const { StdioServerTransport } = require('@modelcontextprotocol/sdk/server/stdio.js');

const server = new Server({
  name: 'passport-ecosystem',
  version: '1.0.0'
}, {
  capabilities: {
    tools: {}
  }
});

// Tool: Query ATP for audit events
server.setToolHandler('query_atp', async (args) => {
  // Connect to your ATP Redis streams
  const events = await fetchATPContext(args.tenantId, args.eventTypes);
  return { events };
});

// Tool: Validate against Policy Router
server.setToolHandler('validate_policy', async (args) => {
  const decision = await fetchPolicyDecision(args.context);
  return { allowed: decision.allowed, reason: decision.reason };
});

// Tool: Check CMC context
server.setToolHandler('get_cmc_context', async (args) => {
  const context = await fetchCMCContext(args.sessionId);
  return { context };
});

const transport = new StdioServerTransport();
server.connect(transport);
```

**Add to Kimi Code**:
```json
{
  "passport-ecosystem": {
    "command": "node",
    "args": ["/home/cory/mcp-passport-server.js"],
    "env": {
      "ATP_ENDPOINT": "https://atp.aetherpro.tech",
      "CMC_ENDPOINT": "https://cmc.aetherpro.tech",
      "POLICY_ROUTER_ENDPOINT": "https://router.aetherpro.tech"
    }
  }
}
```

This gives Kimi **real-time access** to your existing infrastructure during development.

---

## Final Checklist Before "Go"

- [ ] Filesystem MCP points to correct project root
- [ ] GitHub MCP has token with repo access
- [ ] PostgreSQL MCP connection string ready (even if DB not running yet)
- [ ] Docker MCP has socket access (`/var/run/docker.sock`)
- [ ] (Optional) Custom Passport MCP configured with your service endpoints

**Start with Filesystem + GitHub**, add others as phases progress. The 1200-line spec I gave you + these MCPs = Kimi has everything needed for full implementation.

Ready to tell her to go?

#!/usr/bin/env bash
# =============================================================================
# Fabric A2A — Endpoint Test Suite
# =============================================================================
# Usage:
#   chmod +x test_endpoints.sh
#   ./test_endpoints.sh                          # defaults to http://localhost:8000
#   FABRIC_URL=https://fabric.perceptor.us ./test_endpoints.sh
#   MASTER_SECRET=your-secret ./test_endpoints.sh
# =============================================================================

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────
FABRIC_URL="${FABRIC_URL:-https://fabric.perceptor.us}"
MASTER_SECRET="${MASTER_SECRET:-dev-shared-secret}"
AUTH_HEADER="Authorization: Bearer ${MASTER_SECRET}"
CONTENT_TYPE="Content-Type: application/json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

passed=0
failed=0
skipped=0

# ── Helper Functions ──────────────────────────────────────────────────────────

test_endpoint() {
    local method="$1"
    local path="$2"
    local description="$3"
    local data="${4:-}"

    printf "${CYAN}[TEST]${NC} %-8s %-35s %s\n" "$method" "$path" "$description"

    local url="${FABRIC_URL}${path}"
    local http_code
    local response

    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}" -X GET "$url" \
            -H "$AUTH_HEADER" \
            -H "$CONTENT_TYPE" 2>&1) || true
    elif [ "$method" = "POST" ]; then
        response=$(curl -s -w "\n%{http_code}" -X POST "$url" \
            -H "$AUTH_HEADER" \
            -H "$CONTENT_TYPE" \
            -d "$data" 2>&1) || true
    fi

    # Extract HTTP status code (last line) and body (everything else)
    http_code=$(echo "$response" | tail -n1)
    local body=$(echo "$response" | sed '$d')

    if [[ "$http_code" =~ ^2[0-9][0-9]$ ]]; then
        printf "  ${GREEN}✓ PASS${NC} (HTTP %s)\n" "$http_code"
        ((passed++))
    elif [[ "$http_code" =~ ^4[0-9][0-9]$ ]]; then
        printf "  ${YELLOW}⚠ CLIENT ERROR${NC} (HTTP %s)\n" "$http_code"
        ((failed++))
    elif [[ "$http_code" =~ ^5[0-9][0-9]$ ]]; then
        printf "  ${RED}✗ SERVER ERROR${NC} (HTTP %s)\n" "$http_code"
        ((failed++))
    else
        printf "  ${RED}✗ UNREACHABLE${NC} (code: %s)\n" "$http_code"
        ((failed++))
    fi

    # Pretty-print JSON body (truncated)
    if command -v jq &>/dev/null && [ -n "$body" ]; then
        echo "$body" | jq '.' 2>/dev/null | head -20
    else
        echo "$body" | head -10
    fi
    echo ""
}

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║        Fabric A2A — Endpoint Test Suite                  ║"
echo "║        Target: ${FABRIC_URL}                             "
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# =============================================================================
# 1. HEALTH CHECKS
# =============================================================================
echo "━━━ SECTION 1: Health Checks ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_endpoint "GET" "/health" "Root health check"
test_endpoint "GET" "/mcp/health" "MCP server health check"

# =============================================================================
# 2. DOCUMENTATION & SCHEMA
# =============================================================================
echo "━━━ SECTION 2: Documentation ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_endpoint "GET" "/mcp/docs" "Swagger UI docs page"
test_endpoint "GET" "/mcp/docs/json" "OpenAPI JSON schema"

# =============================================================================
# 3. AGENT REGISTRY
# =============================================================================
echo "━━━ SECTION 3: Agent Registry ━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# List all agents
test_endpoint "GET" "/mcp/list_agents" "List all registered agents"

# Register a test agent
test_endpoint "POST" "/mcp/register_agent" "Register test agent" '{
    "agent_id": "test-agent-001",
    "display_name": "Test Agent",
    "version": "1.0.0",
    "capabilities": [
        {
            "name": "echo",
            "description": "Echo back messages for testing"
        },
        {
            "name": "healthcheck",
            "description": "Report agent health status"
        }
    ],
    "endpoint": {
        "transport": "http",
        "uri": "http://localhost:9001/mcp"
    }
}'

# Get specific agent details
test_endpoint "GET" "/mcp/agent/test-agent-001" "Get test agent details"

# Register Aether Agent (your real agent)
test_endpoint "POST" "/mcp/register_agent" "Register Aether Agent" '{
    "agent_id": "aether-agent",
    "display_name": "Aether Agent",
    "version": "1.0.0",
    "capabilities": [
        {
            "name": "reason",
            "description": "Advanced reasoning and analysis"
        },
        {
            "name": "orchestrate",
            "description": "Coordinate multi-agent workflows"
        },
        {
            "name": "code",
            "description": "Code generation and review"
        }
    ],
    "endpoint": {
        "transport": "http",
        "uri": "http://aetheros.local:8080/mcp"
    }
}'

# List agents again to verify registration
test_endpoint "GET" "/mcp/list_agents" "Verify agents registered"

# =============================================================================
# 4. TOOLS
# =============================================================================
echo "━━━ SECTION 4: Tools ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# List available tools
test_endpoint "GET" "/mcp/list_tools" "List all built-in tools"

# =============================================================================
# 5. TOPICS / PUB-SUB
# =============================================================================
echo "━━━ SECTION 5: Topics / Pub-Sub ━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_endpoint "GET" "/mcp/list_topics" "List active Pub/Sub topics"

# =============================================================================
# 6. METRICS
# =============================================================================
echo "━━━ SECTION 6: Metrics ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

test_endpoint "GET" "/mcp/metrics" "Prometheus metrics"

# =============================================================================
# 7. MCP CALLS (Agent-to-Agent Communication)
# =============================================================================
echo "━━━ SECTION 7: MCP Calls ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# fabric.call — delegate task to an agent
test_endpoint "POST" "/mcp/call" "fabric.call — delegate task" '{
    "name": "fabric.call",
    "arguments": {
        "agent_id": "aether-agent",
        "capability": "reason",
        "task": "Analyze the current system health and provide a summary",
        "context": {
            "source": "test-suite",
            "priority": "low"
        },
        "stream": false,
        "timeout_ms": 30000
    }
}'

# fabric.tool.call — execute a built-in tool
test_endpoint "POST" "/mcp/call" "fabric.tool.call — calculator" '{
    "name": "fabric.tool.call",
    "arguments": {
        "tool_id": "math.calculate",
        "capability": "calculate",
        "parameters": {
            "expression": "2 + 2 * 10"
        }
    }
}'

# fabric.agent.list — list agents via MCP
test_endpoint "POST" "/mcp/call" "fabric.agent.list via MCP" '{
    "name": "fabric.agent.list",
    "arguments": {}
}'

# fabric.agent.describe — get agent details via MCP
test_endpoint "POST" "/mcp/call" "fabric.agent.describe via MCP" '{
    "name": "fabric.agent.describe",
    "arguments": {
        "agent_id": "aether-agent"
    }
}'

# fabric.tool.list — list tools via MCP
test_endpoint "POST" "/mcp/call" "fabric.tool.list via MCP" '{
    "name": "fabric.tool.list",
    "arguments": {}
}'

# =============================================================================
# 8. ASYNC MESSAGING
# =============================================================================
echo "━━━ SECTION 8: Async Messaging ━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Send a message between agents
test_endpoint "POST" "/mcp/call" "fabric.message.send" '{
    "name": "fabric.message.send",
    "arguments": {
        "from_agent": "test-agent-001",
        "to_agent": "aether-agent",
        "message_type": "task",
        "payload": {
            "task_type": "echo",
            "content": "Hello from the test suite!",
            "priority": "normal"
        }
    }
}'

# Receive messages for an agent
test_endpoint "POST" "/mcp/call" "fabric.message.receive" '{
    "name": "fabric.message.receive",
    "arguments": {
        "agent_id": "aether-agent",
        "count": 5,
        "block_ms": 1000
    }
}'

# =============================================================================
# SUMMARY
# =============================================================================
echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                    TEST SUMMARY                          ║"
echo "╠══════════════════════════════════════════════════════════╣"
printf "║  ${GREEN}Passed: %3d${NC}                                            ║\n" "$passed"
printf "║  ${RED}Failed: %3d${NC}                                            ║\n" "$failed"
echo "║                                                          ║"
echo "║  Total:  $((passed + failed))                                              "
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Exit with error if any tests failed
[ "$failed" -eq 0 ] && exit 0 || exit 1

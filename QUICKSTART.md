# Fabric MCP Server - Quickstart Guide

Get up and running with the Fabric MCP Server in 5 minutes.

## Prerequisites

- Python 3.11 or higher
- pip or uv package manager

## Installation

```bash
# Navigate to the project directory
cd a2a-mcp

# Install dependencies
pip install -r requirements.txt

# Or using uv (faster)
run `uv venv` to create an environment
run source .venv/bin/activate to activate environment
uv pip install -r requirements.txt
```

## Start the Server

### Option 1: STDIO Transport (for local MCP clients)

```bash
python server.py --transport stdio --config agents.yaml
```

This mode is ideal for integrating with MCP clients like Claude Desktop.

### Option 2: HTTP Transport (for remote access)

```bash
python server.py --transport http --port 8000 --config agents.yaml
```

The server will start on `http://localhost:8000`.

## Test the Server

Open a new terminal and run the example client:

```bash
python example_client.py
```

You should see output showing:
- Server health check
- List of registered agents
- Agent descriptions
- Example agent calls

## Make Your First Agent Call

### Using curl

```bash
curl -H "Authorization: Bearer dev-shared-secret" \
  -X POST http://localhost:8000/mcp/call \
  -d '{
    "name": "fabric.call",
    "arguments": {
      "agent_id": "percy",
      "capability": "reason",
      "task": "Explain the benefits of microservices architecture"
    }
  }'
```

### Using Python

```python
import requests

response = requests.post(
    "http://localhost:8000/mcp/call",
    headers={"Authorization": "Bearer dev-shared-secret"},
    json={
        "name": "fabric.call",
        "arguments": {
            "agent_id": "percy",
            "capability": "reason",
            "task": "What is quantum computing?"
        }
    }
)

print(response.json())
```

## Available MCP Tools

| Tool | Description |
| :--- | :--- |
| `fabric.agent.list` | List all registered agents |
| `fabric.agent.describe` | Get detailed info about an agent |
| `fabric.call` | Call an agent's capability |
| `fabric.route.preview` | Preview routing for debugging |
| `fabric.health` | Check server health |

## Next Steps

1. **Read the full documentation**: See [README.md](README.md) for comprehensive usage instructions
2. **Explore the architecture**: Check out [architecture.md](architecture.md) for system design details
3. **Integrate your own agent**: Follow the [integration_guide.md](integration_guide.md)
4. **Review the schemas**: See [schemas.json](schemas.json) for complete MCP tool definitions

## Common Issues

### "Connection refused" error

Make sure the server is running on the correct port:
```bash
python server.py --transport http --port 8000
```

### "Authentication failed" error

Ensure you're passing the correct PSK in the Authorization header:
```bash
-H "Authorization: Bearer dev-shared-secret"
```

### Agent shows as "offline"

The example agents in `agents.yaml` are mock endpoints. In production, you would replace these with real agent endpoints. The server will still respond with mock data for testing.

## Development Mode

For development, you can modify `agents.yaml` to add your own agents. The server will load the configuration on startup.

Example minimal agent entry:

```yaml
- agent_id: my-agent
  display_name: My Agent
  version: 1.0.0
  runtime: mcp
  endpoint:
    transport: http
    uri: http://localhost:9000/mcp
  capabilities:
    - name: my_capability
      description: Does something useful
      streaming: false
  tags: [custom]
  trust_tier: local
```

## Support

- Full documentation: [README.md](README.md)
- Architecture details: [architecture.md](architecture.md)
- Integration guide: [integration_guide.md](integration_guide.md)
- Tool schemas: [schemas.json](schemas.json)

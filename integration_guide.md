# Fabric MCP Server: Agent Integration Guide

This guide provides instructions for agent developers on how to register and integrate their agents with the Fabric MCP Server. By following these steps, your agent can become a discoverable and callable tool within the agent-to-agent communication network.

## 1. Integration Overview

Integrating an agent with the Fabric server involves two main steps:

1.  **Creating an Agent Manifest**: You define your agent's identity, capabilities, and endpoint in the central `agents.yaml` registry file. This makes your agent discoverable.
2.  **Implementing the Agent Runtime**: You expose your agent's capabilities over a network protocol that the Fabric server can communicate with. This can be native MCP or any other protocol for which a [Runtime Adapter](#4-implementing-a-custom-agent-with-an-adapter) exists or can be written.

```
┌──────────────────┐      ┌───────────────────────────┐      ┌──────────────────┐
│   Your Agent     │ ◄─── │   Fabric Runtime Adapter  │ ◄─── │  Fabric Gateway  │
│ (e.g., HTTP API) │      │ (e.g., RuntimeCustomHTTP) │      │   (MCP Tools)    │
└──────────────────┘      └───────────────────────────┘      └──────────────────┘
         ▲
         │
         └─────────────────┐
                           ▼
                  ┌──────────────────┐
                  │   Agent Registry │
                  │   (agents.yaml)  │
                  └──────────────────┘
```

## 2. Creating Your Agent Manifest

The first step is to add an entry for your agent in the `agents.yaml` file. This manifest tells the Fabric server everything it needs to know to route requests to your agent.

### Manifest Structure

Each agent entry is a YAML object with the following fields:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `agent_id` | String | Yes | A unique, URL-safe identifier for your agent (e.g., `my-awesome-agent`). |
| `display_name` | String | No | A human-readable name for your agent (e.g., "My Awesome Agent"). Defaults to `agent_id`. |
| `version` | String | No | The semantic version of your agent (e.g., `1.0.0`). |
| `description` | String | No | A brief description of what your agent does. |
| `runtime` | String | No | The runtime adapter to use. Defaults to `mcp`. Other options include `agentzero`. |
| `endpoint` | Object | Yes | Defines how to connect to your agent. |
| `capabilities` | Array | Yes | A list of the capabilities your agent provides. |
| `tags` | Array | No | A list of searchable tags for categorization (e.g., `[data-analysis, python]`). |
| `trust_tier` | String | No | The trust level (`local`, `org`, `public`). Defaults to `org`. |

### Endpoint Configuration

The `endpoint` object specifies the connection details:

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `transport` | String | Yes | The protocol to use (`http`, `ws`, `local`, `stdio`). |
| `uri` | String | Yes | The connection URI (e.g., `http://my-agent-service:8080/call`). |

### Capability Definition

The `capabilities` array is the most important part of the manifest. Each capability is an object that defines a specific function your agent can perform.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `name` | String | Yes | The name of the capability (e.g., `analyze_sentiment`). |
| `description` | String | No | A clear, concise description of the capability. |
| `streaming` | Boolean | No | Set to `true` if the capability can stream responses. Defaults to `false`. |
| `modalities` | Array | No | A list of supported data modalities (e.g., `[text, image]`). Defaults to `[text]`. |
| `input_schema` | Object | No | A JSON Schema object defining the expected input arguments. |
| `output_schema`| Object | No | A JSON Schema object defining the structure of the successful output. |
| `max_timeout_ms` | Integer | No | The maximum time in milliseconds this capability can run. Defaults to `60000`. |

### Example Manifest

```yaml
- agent_id: sentiment-analyzer
  display_name: Sentiment Analyzer
  version: 1.1.0
  description: Analyzes the sentiment of a given text.
  runtime: mcp
  endpoint:
    transport: http
    uri: http://sentiment-agent.internal:8000/mcp
  capabilities:
    - name: analyze
      description: Analyzes input text and returns a sentiment score.
      streaming: false
      input_schema:
        type: object
        properties:
          text:
            type: string
            description: The text to analyze.
        required: [text]
      output_schema:
        type: object
        properties:
          sentiment:
            type: string
            enum: [positive, negative, neutral]
          score:
            type: number
            description: Confidence score between -1 and 1.
  tags: [nlp, text-analysis]
  trust_tier: org
```

## 3. Implementing a Native MCP Agent

If you set `runtime: mcp` in your manifest, the Fabric server expects your agent to expose an MCP-compliant endpoint. This is the most direct way to integrate.

Your agent must:
1.  Expose an HTTP endpoint that accepts POST requests at the `uri` specified in the manifest.
2.  Expect a JSON payload corresponding to an MCP tool call.
3.  Process the request and return a JSON response in the format expected by the Fabric server.

### Expected Request Format

When a user calls `fabric.call`, your agent will receive a request that looks like this. Note that the Fabric server translates the `fabric.call` into a direct call to your agent's capability.

**Request to `http://sentiment-agent.internal:8000/mcp`:**
```json
{
  "name": "analyze",
  "arguments": {
    "text": "I love the new Fabric server! It's so easy to use."
  }
}
```

### Expected Response Format

Your agent must return a JSON object with the results of the execution.

**Synchronous Response:**
```json
{
  "ok": true,
  "result": {
    "sentiment": "positive",
    "score": 0.95
  }
}
```

**Error Response:**
If something goes wrong, return a structured error.
```json
{
  "ok": false,
  "error": {
    "code": "INVALID_INPUT",
    "message": "The provided text was empty."
  }
}
```

### Example Agent (FastAPI)

Here is a minimal agent implementation using FastAPI.

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class AnalyzeArguments(BaseModel):
    text: str

class ToolCall(BaseModel):
    name: str
    arguments: AnalyzeArguments

@app.post("/mcp")
def handle_mcp_call(call: ToolCall):
    if call.name == "analyze":
        if not call.arguments.text:
            return {
                "ok": false,
                "error": {"code": "INVALID_INPUT", "message": "Text cannot be empty."}
            }
        
        # Dummy sentiment analysis logic
        sentiment = "positive"
        score = 0.95
        if "hate" in call.arguments.text.lower():
            sentiment = "negative"
            score = -0.8
        
        return {
            "ok": true,
            "result": {
                "sentiment": sentiment,
                "score": score
            }
        }
    else:
        return {
            "ok": false,
            "error": {"code": "CAPABILITY_NOT_FOUND", "message": f"Capability {call.name} not found."}
        }
```

## 4. Implementing a Custom Agent with an Adapter

If your agent doesn't speak MCP natively, you can use a different `runtime` in your manifest and rely on a **Runtime Adapter** to translate requests.

For example, if your agent has a simple REST API, you could create a `RuntimeCustomHTTP` adapter.

1.  **Update Manifest**: Change `runtime` to a custom identifier (e.g., `custom-http`).

    ```yaml
    - agent_id: legacy-agent
      runtime: custom-http
      endpoint:
        transport: http
        uri: http://legacy-agent/api/v1/action
      ...
    ```

2.  **Create an Adapter**: Write a Python class that inherits from `RuntimeAdapter` and implements the translation logic.

    ```python
    # In server.py or a separate adapters.py file
    import aiohttp

    class RuntimeCustomHTTP(RuntimeAdapter):
        async def call(self, envelope: CanonicalEnvelope) -> Dict[str, Any]:
            # 1. Translate Fabric envelope to the agent's expected format
            custom_request_payload = {
                "action_name": envelope.target["capability"],
                "params": envelope.input["context"],
                "trace_id": envelope.trace.trace_id
            }

            # 2. Make the HTTP call to the agent
            async with aiohttp.ClientSession() as session:
                async with session.post(self.endpoint.uri, json=custom_request_payload) as response:
                    if response.status != 200:
                        raise FabricError(ErrorCode.UPSTREAM_ERROR, f"Agent returned status {response.status}")
                    agent_response = await response.json()

            # 3. Translate the agent's response back to the Fabric format
            return {
                "ok": True,
                "trace": envelope.trace.to_dict(),
                "result": agent_response.get("data", {})
            }
    ```

3.  **Register the Adapter**: In `server.py`, modify `load_registry_from_yaml` to recognize your new runtime.

    ```python
    # In server.py -> load_registry_from_yaml()
    ...
    runtime_type = agent_config.get("runtime", "mcp")
    if runtime_type == "mcp":
        adapter = RuntimeMCP(manifest.agent_id, endpoint, manifest)
    elif runtime_type == "agentzero":
        adapter = RuntimeAgentZero(manifest.agent_id, endpoint, manifest)
    elif runtime_type == "custom-http": # Add this
        adapter = RuntimeCustomHTTP(manifest.agent_id, endpoint, manifest)
    else:
        adapter = RuntimeMCP(manifest.agent_id, endpoint, manifest)
    
    registry.register(manifest, adapter)
    ```

## 5. Authentication

The Fabric server handles authentication at the gateway. Your agent does not need to implement complex authentication logic, but it can perform optional re-verification.

-   **PSK (Pre-Shared Key)**: The gateway validates the PSK. The call is either accepted or rejected before it reaches your agent.
-   **Passport (Future)**: The gateway will verify the cryptographic signature of the passport. The verified identity and permissions will be passed in the `CanonicalEnvelope`'s `auth` context. Your agent can optionally re-verify the signature or trust the gateway's validation.

Your agent's primary responsibility is to execute the task. You can assume that any request received from the Fabric gateway has already been authenticated.

## 6. Implementing Streaming

If your agent's capability is long-running or can produce incremental results, you should enable streaming.

1.  **Manifest**: Set `streaming: true` for the capability.
2.  **Agent Implementation**: Your agent must return a stream of Server-Sent Events (SSE).

### SSE Event Format

Each event must be a JSON object with an `event` type and a `data` payload.

| Event Type | Data Payload Description |
| :--- | :--- |
| `status` | Indicates a change in the execution status (e.g., `running`, `complete`). |
| `token` | An incremental text token (e.g., a word or sentence). |
| `tool_call` | A request for the client to call another tool. |
| `progress` | A progress update (e.g., `{ "percent": 50, "message": "Halfway done" }`). |
| `final` | The final result of the execution, sent as the last event. |

### Example Streaming Agent (FastAPI)

```python
import asyncio
import json
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()

async def stream_generator():
    events = [
        {"event": "status", "data": {"status": "running"}},
        {"event": "token", "data": {"text": "Starting analysis... "}},
        await asyncio.sleep(1),
        {"event": "progress", "data": {"percent": 50, "message": "Analyzing data"}},
        {"event": "token", "data": {"text": "Almost done... "}},
        await asyncio.sleep(1),
        {"event": "final", "data": {"ok": True, "result": {"summary": "Analysis complete."}}}
    ]
    for event in events:
        yield f"data: {json.dumps(event)}\n\n"

@app.post("/mcp_stream")
def handle_streaming_call():
    return StreamingResponse(stream_generator(), media_type="text/event-stream")
```

## 7. Best Practices

-   **Statelessness**: Design your agent capabilities to be as stateless as possible. Rely on the input context for all necessary information.
-   **Idempotency**: If possible, make your capabilities idempotent. If the Fabric server retries a request due to a network issue, it should not cause duplicate actions.
-   **Clear Schemas**: Provide detailed and accurate `input_schema` and `output_schema` in your manifest. This enables better validation and client-side integration.
-   **Informative Errors**: Return meaningful error codes and messages. This helps users and other agents debug issues.
-   **Health Checks**: Implement a simple health check endpoint that the Fabric server can use to monitor your agent's status.
-   **Logging**: Log all incoming requests and outgoing responses with the `trace_id` provided in the envelope to aid in distributed tracing.

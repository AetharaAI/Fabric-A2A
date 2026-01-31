# Fabric MCP Server - Universal Tool Inventory

Fabric now serves as both an **Agent-to-Agent Communication Gateway** and a **Universal Tool Server**. This document describes the built-in tool inventory that any MCP-compatible client can use.

## Overview

The Fabric tool inventory provides **20+ built-in tools** organized into 8 categories:

| Category | Tools | Description |
|----------|-------|-------------|
| **io** | 4 tools | File system operations |
| **web** | 3 tools | HTTP requests, web scraping |
| **math** | 2 tools | Calculations, statistics |
| **text** | 3 tools | Regex, transformations, diff |
| **system** | 3 tools | Commands, environment, datetime |
| **data** | 3 tools | JSON, CSV, validation |
| **security** | 2 tools | Hashing, encoding |
| **encoding** | 1 tool | URL encoding |
| **docs** | 1 tool | Markdown processing |

## Quick Start

### 1. List All Available Tools
```python
client.list_tools()
```

### 2. Call a Built-in Tool
```python
# Direct call
client._call_tool("fabric.tool.io.read_file", {"path": "./config.json"})

# Or use the convenience method
client.read_file("./config.json")
```

### 3. Filter Tools by Category
```python
client.list_tools(category="math")
client.list_tools(provider="builtin")
```

---

## I/O Tools (`io.*`)

File system operations with security restrictions.

### `io.read_file`
Read file contents with optional line limits.

**Capability:** `read`

**Input:**
```json
{
  "path": "./data.txt",
  "max_lines": 100,
  "encoding": "utf-8"
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "content": "file contents...",
    "line_count": 50,
    "truncated": false,
    "path": "/absolute/path/data.txt",
    "size": 1024
  }
}
```

### `io.write_file`
Write content to a file (creates directories if needed).

**Capability:** `write`

**Input:**
```json
{
  "path": "./output.txt",
  "content": "Hello, World!",
  "append": false
}
```

### `io.list_directory`
List directory contents with optional filtering.

**Capability:** `list`

**Input:**
```json
{
  "path": ".",
  "recursive": false,
  "pattern": "*.py"
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "path": "/current/dir",
    "entries": [
      {"name": "main.py", "type": "file", "size": 1024, "modified": "2026-01-31T10:00:00Z"},
      {"name": "utils", "type": "directory", "size": null, "modified": "2026-01-31T09:00:00Z"}
    ],
    "count": 2
  }
}
```

### `io.search_files`
Search file contents using regex (streaming).

**Capability:** `search`

**Input:**
```json
{
  "path": "./src",
  "pattern": "def \w+\(",
  "file_pattern": "*.py"
}
```

---

## Web Tools (`web.*`)

HTTP requests and web page processing.

### `web.http_request`
Make HTTP requests (GET, POST, PUT, DELETE, PATCH).

**Capability:** `request`

**Input:**
```json
{
  "url": "https://api.example.com/data",
  "method": "POST",
  "headers": {"Authorization": "Bearer token"},
  "body": "{\"key\": \"value\"}",
  "timeout": 30000
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "status_code": 200,
    "headers": {"content-type": "application/json"},
    "body": "{\"result\": \"success\"}",
    "elapsed_ms": 150,
    "url": "https://api.example.com/data"
  }
}
```

### `web.fetch_page`
Fetch and extract readable content from web pages.

**Capability:** `fetch`

**Input:**
```json
{
  "url": "https://example.com/article",
  "extract_text": true,
  "max_length": 50000
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "title": "Article Title",
    "text": "Extracted article content...",
    "links": ["https://example.com/link1", "https://example.com/link2"],
    "metadata": {
      "content_type": "text/html; charset=utf-8",
      "length": 15320
    }
  }
}
```

### `web.parse_url`
Parse URL into components.

**Capability:** `parse_url`

**Input:**
```json
{
  "url": "https://user:pass@example.com:8080/path?query=value#fragment"
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "scheme": "https",
    "netloc": "user:pass@example.com:8080",
    "path": "/path",
    "params": "",
    "query": {"query": "value"},
    "fragment": "fragment",
    "hostname": "example.com",
    "port": 8080
  }
}
```

---

## Math Tools (`math.*`)

Mathematical calculations and statistics.

### `math.calculate`
Safely evaluate mathematical expressions.

**Capability:** `eval`

**Input:**
```json
{
  "expression": "(2 + 3) * 4 / sqrt(16)",
  "precision": 10
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "result": 5.0,
    "expression": "(2 + 3) * 4 / sqrt(16)",
    "type": "float"
  }
}
```

**Supported Functions:**
- Basic: `abs`, `round`, `max`, `min`, `sum`, `pow`, `len`
- Trig: `sin`, `cos`, `tan`, `asin`, `acos`, `atan`
- Math: `sqrt`, `log`, `log10`, `exp`, `ceil`, `floor`
- Constants: `pi`, `e`

### `math.statistics`
Calculate statistical measures on datasets.

**Capability:** `analyze`

**Input:**
```json
{
  "data": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
  "measures": ["mean", "median", "stddev", "min", "max", "count", "sum"]
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "count": 10,
    "sum": 55,
    "mean": 5.5,
    "median": 5.5,
    "stddev": 2.872281323,
    "min": 1,
    "max": 10
  }
}
```

---

## Text Tools (`text.*`)

Text processing and transformation.

### `text.regex`
Pattern matching with regular expressions.

**Capability:** `match`

**Input:**
```json
{
  "text": "Email: user@example.com, Phone: 123-456-7890",
  "pattern": "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b",
  "flags": ["i"]
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "matches": ["user@example.com"],
    "groups": [],
    "count": 1,
    "pattern": "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b"
  }
}
```

### `text.transform`
Apply text transformations.

**Capability:** `transform`

**Operations:** `uppercase`, `lowercase`, `trim`, `truncate`, `replace`, `split`, `join`

**Input:**
```json
{
  "text": "  Hello, World!  ",
  "operations": [
    {"type": "trim"},
    {"type": "uppercase"},
    {"type": "replace", "old": "WORLD", "new": "FABRIC"}
  ]
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "result": "HELLO, FABRIC!",
    "operations_applied": 3
  }
}
```

### `text.diff`
Compare two texts and show differences.

**Capability:** `compare`

**Input:**
```json
{
  "original": "Line 1\nLine 2\nLine 3",
  "modified": "Line 1\nLine 2 modified\nLine 3\nLine 4",
  "context_lines": 3
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "diff": "--- original\n+++ modified\n@@ -1,3 +1,4 @@\n Line 1\n-Line 2\n+Line 2 modified\n Line 3\n+Line 4",
    "added": 1,
    "removed": 1,
    "unchanged": 2,
    "total_changes": 2
  }
}
```

---

## System Tools (`system.*`)

Command execution and system information.

### `system.execute`
Execute shell commands safely (sandboxed).

**Capability:** `exec`

**⚠️ Security Note:** Commands are validated against dangerous patterns. Requires `trust_tier: local`.

**Input:**
```json
{
  "command": "ls -la",
  "working_dir": "/home/user",
  "timeout": 30000,
  "env": {"CUSTOM_VAR": "value"}
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "stdout": "total 128\ndrwxr-xr-x 5 user user 4096 Jan 31 10:00 .\n...",
    "stderr": "",
    "exit_code": 0,
    "duration_ms": 50,
    "command": "ls -la"
  }
}
```

### `system.env`
Get environment variables.

**Capability:** `get`

**Input:**
```json
{
  "name": "PATH"
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "name": "PATH",
    "value": "/usr/local/bin:/usr/bin:/bin",
    "exists": true
  }
}
```

### `system.datetime`
Get current time in various formats.

**Capability:** `now`

**Input:**
```json
{
  "timezone": "UTC",
  "format": "iso"
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "iso": "2026-01-31T10:30:00+00:00",
    "timestamp": 1738324200.0,
    "formatted": "2026-01-31T10:30:00+00:00",
    "timezone": "UTC"
  }
}
```

---

## Data Tools (`data.*`)

JSON, CSV, and schema validation.

### `data.json`
Parse JSON and query with JSONPath.

**Capability:** `parse`

**Input:**
```json
{
  "json": "{\"users\": [{\"name\": \"Alice\"}, {\"name\": \"Bob\"}]}",
  "query": "$.users[0].name"
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "data": "Alice",
    "valid": true,
    "type": "str"
  }
}
```

### `data.csv`
Parse CSV to array of objects.

**Capability:** `csv_parse`

**Input:**
```json
{
  "csv": "name,age,city\nAlice,30,NYC\nBob,25,LA",
  "delimiter": ",",
  "headers": true
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "rows": [
      {"name": "Alice", "age": "30", "city": "NYC"},
      {"name": "Bob", "age": "25", "city": "LA"}
    ],
    "headers": ["name", "age", "city"],
    "row_count": 2
  }
}
```

### `data.validate`
Validate data against JSON Schema.

**Capability:** `validate`

**Input:**
```json
{
  "data": {"name": "Alice", "age": 30},
  "schema": {
    "type": "object",
    "properties": {
      "name": {"type": "string"},
      "age": {"type": "integer", "minimum": 0}
    },
    "required": ["name", "age"]
  }
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "valid": true,
    "errors": []
  }
}
```

---

## Security Tools (`security.*`)

Cryptographic hashing and encoding.

### `security.hash`
Generate cryptographic hashes.

**Capability:** `hash`

**Algorithms:** `md5`, `sha1`, `sha256`, `sha512`

**Input:**
```json
{
  "data": "Hello, World!",
  "algorithm": "sha256"
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "hash": "dffd6021bb2bd5b0af676290809ec3a53191dd81c7f70a4b28688a362182986f",
    "algorithm": "sha256",
    "bytes": 32
  }
}
```

### `security.base64`
Base64 encode/decode.

**Capability:** `encode`

**Input:**
```json
{
  "data": "Hello, World!",
  "decode": false
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "result": "SGVsbG8sIFdvcmxkIQ==",
    "operation": "encode"
  }
}
```

---

## Encoding Tools (`encode.*`)

### `encode.url`
URL encode/decode strings.

**Capability:** `encode`

**Input:**
```json
{
  "text": "hello world!@#$%",
  "decode": false
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "result": "hello%20world%21%40%23%24%25",
    "operation": "encode",
    "original_length": 16,
    "result_length": 28
  }
}
```

---

## Documentation Tools (`docs.*`)

### `docs.markdown`
Process Markdown to HTML and extract structure.

**Capability:** `process`

**Input:**
```json
{
  "markdown": "# Title\n\n## Section 1\n\nSome **bold** text.",
  "extract_toc": true
}
```

**Output:**
```json
{
  "ok": true,
  "result": {
    "html": "<p><h1>Title</h1></p><p><h2>Section 1</h2></p><p>Some <b>bold</b> text.</p>",
    "headings": [
      {"level": 1, "title": "Title", "anchor": "title"},
      {"level": 2, "title": "Section 1", "anchor": "section-1"}
    ],
    "heading_count": 2,
    "toc": [
      {"level": 1, "title": "Title", "anchor": "title"},
      {"level": 2, "title": "Section 1", "anchor": "section-1"}
    ]
  }
}
```

---

## MCP Tool Interface

### New MCP Tools Added

In addition to the original `fabric.*` tools, the following are now available:

#### `fabric.tool.list`
List all available tools (both built-in and agent-based).

**Input:**
```json
{
  "category": "math",      // Optional: filter by category
  "provider": "builtin"    // Optional: 'builtin' or 'agent'
}
```

#### `fabric.tool.call`
Execute a built-in tool or agent capability.

**Input:**
```json
{
  "tool_id": "io.read_file",
  "capability": "read",
  "parameters": {
    "path": "./file.txt"
  }
}
```

#### `fabric.tool.describe`
Get detailed information about a tool.

**Input:**
```json
{
  "tool_id": "io.read_file"
}
```

#### Direct Tool Calls
You can also call tools directly:
```json
{
  "name": "fabric.tool.io.read_file",
  "arguments": {"path": "./file.txt"}
}
```

---

## Architecture

### How It Works

```
MCP Client → Fabric Server
                ↓
        ┌──────┴──────┐
        │             │
   Built-in Tool   Remote Agent
   (io, web, etc)  (percy, coder)
```

1. Client calls `fabric.tool.*`
2. Fabric checks if it's a built-in tool or remote agent
3. Built-in tools execute directly in the server
4. Remote agents are called via `fabric.call` routing

### Security

- Built-in tools have security restrictions (e.g., file access limits)
- Dangerous system commands are blocked
- Sensitive environment variables are filtered
- Trust tiers control access to system tools

---

## Example Usage

### Python Client
```python
from example_client import FabricClient

client = FabricClient("http://localhost:8000", "your-secret")

# List all tools
tools = client.list_tools()
print(f"Available tools: {tools['count']}")

# Read a file
result = client.read_file("./README.md")
print(result['result']['content'])

# Calculate
result = client.calculate("sqrt(144) * 2")
print(result['result']['result'])  # 24.0

# Make HTTP request
result = client.http_request("https://api.github.com/users/octocat")
print(result['result']['body'])

# Hash data
result = client.hash_string("password123", "sha256")
print(result['result']['hash'])
```

### curl
```bash
# List tools
curl -H "Authorization: Bearer secret" \
  -X POST http://localhost:8000/mcp/call \
  -d '{"name": "fabric.tool.list", "arguments": {}}'

# Calculate
curl -H "Authorization: Bearer secret" \
  -X POST http://localhost:8000/mcp/call \
  -d '{
    "name": "fabric.tool.math.calculate",
    "arguments": {"expression": "2 + 2"}
  }'

# Read file
curl -H "Authorization: Bearer secret" \
  -X POST http://localhost:8000/mcp/call \
  -d '{
    "name": "fabric.tool.io.read_file",
    "arguments": {"path": "./README.md"}
  }'
```

---

## Roadmap

### Future Tools
- **Database tools** (`db.*`) - SQL queries, connection pooling
- **Cache tools** (`cache.*`) - Redis, in-memory caching
- **Queue tools** (`queue.*`) - Message queue operations
- **Image tools** (`image.*`) - Resize, convert, analyze
- **PDF tools** (`pdf.*`) - Extract text, merge, split
- **Git tools** (`git.*`) - Clone, commit, diff
- **Docker tools** (`docker.*`) - Container operations

---

## Contributing

To add a new built-in tool:

1. Add tool class to `tools/builtin_tools.py`
2. Register in `BUILTIN_TOOLS` dictionary
3. Add definition to `agents.yaml` under `tools:`
4. Update this documentation

---

**Built-in tools make Fabric a true Universal MCP Tool Server - any capability an agent needs is just a tool call away!**
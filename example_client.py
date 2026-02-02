#!/usr/bin/env python3
"""
Example client for the Fabric MCP Server
Demonstrates how to interact with the agent-to-agent gateway
"""

import json
import requests
from typing import Dict, Any, Optional


class FabricClient:
    """Simple client for Fabric MCP Server"""
    
    def __init__(self, base_url: str = "http://localhost:8000", auth_token: str = "dev-shared-secret"):
        self.base_url = base_url
        self.auth_token = auth_token
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def _call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Make a tool call to the Fabric server"""
        response = requests.post(
            f"{self.base_url}/mcp/call",
            headers=self.headers,
            json={
                "name": tool_name,
                "arguments": arguments
            }
        )
        response.raise_for_status()
        return response.json()
    
    def list_agents(self, capability: Optional[str] = None, 
                   tag: Optional[str] = None, 
                   status: Optional[str] = None) -> Dict[str, Any]:
        """List all registered agents"""
        filter_args = {}
        if capability:
            filter_args["capability"] = capability
        if tag:
            filter_args["tag"] = tag
        if status:
            filter_args["status"] = status
        
        return self._call_tool("fabric.agent.list", {"filter": filter_args})
    
    def describe_agent(self, agent_id: str) -> Dict[str, Any]:
        """Get detailed information about an agent"""
        return self._call_tool("fabric.agent.describe", {"agent_id": agent_id})
    
    def call_agent(self, agent_id: str, capability: str, task: str, 
                  context: Optional[Dict[str, Any]] = None,
                  stream: bool = False,
                  timeout_ms: int = 60000) -> Dict[str, Any]:
        """Call an agent's capability"""
        arguments = {
            "agent_id": agent_id,
            "capability": capability,
            "task": task,
            "stream": stream,
            "timeout_ms": timeout_ms
        }
        if context:
            arguments["context"] = context
        
        return self._call_tool("fabric.call", arguments)
    
    def preview_route(self, agent_id: str, capability: str) -> Dict[str, Any]:
        """Preview where a call would be routed"""
        return self._call_tool("fabric.route.preview", {
            "agent_id": agent_id,
            "capability": capability
        })
    
    def health(self) -> Dict[str, Any]:
        """Check Fabric server health"""
        return self._call_tool("fabric.health", {})
    
    # Built-in Tool Methods
    
    def list_tools(self, category: Optional[str] = None, provider: Optional[str] = None) -> Dict[str, Any]:
        """List all available tools (built-in and agents)"""
        args = {}
        if category:
            args["category"] = category
        if provider:
            args["provider"] = provider
        return self._call_tool("fabric.tool.list", args)
    
    def call_tool(self, tool_id: str, capability: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call a built-in tool directly"""
        return self._call_tool("fabric.tool.call", {
            "tool_id": tool_id,
            "capability": capability,
            "parameters": parameters or {}
        })
    
    def read_file(self, path: str, max_lines: Optional[int] = None) -> Dict[str, Any]:
        """Read a file using built-in tool"""
        return self._call_tool("fabric.tool.io.read_file", {
            "path": path,
            "max_lines": max_lines
        })
    
    def write_file(self, path: str, content: str, append: bool = False) -> Dict[str, Any]:
        """Write to a file using built-in tool"""
        return self._call_tool("fabric.tool.io.write_file", {
            "path": path,
            "content": content,
            "append": append
        })
    
    def http_request(self, url: str, method: str = 'GET', headers: Optional[Dict] = None, 
                     body: Optional[str] = None) -> Dict[str, Any]:
        """Make HTTP request using built-in tool"""
        args = {"url": url, "method": method}
        if headers:
            args["headers"] = headers
        if body:
            args["body"] = body
        return self._call_tool("fabric.tool.web.http_request", args)
    
    def calculate(self, expression: str) -> Dict[str, Any]:
        """Calculate expression using built-in tool"""
        return self._call_tool("fabric.tool.math.calculate", {"expression": expression})
    
    def hash_string(self, data: str, algorithm: str = 'sha256') -> Dict[str, Any]:
        """Generate hash using built-in tool"""
        return self._call_tool("fabric.tool.security.hash", {
            "data": data,
            "algorithm": algorithm
        })
    
    def base64_encode(self, data: str, decode: bool = False) -> Dict[str, Any]:
        """Base64 encode/decode using built-in tool"""
        return self._call_tool("fabric.tool.security.base64", {
            "data": data,
            "decode": decode
        })
    
    def brave_search(self, query: str, recency_days: int = 7, max_results: int = 5):
        """Perform a Brave web search using built-in tool"""
        return self._call_tool(
            "fabric.tool.call",
            {
                "tool_id": "web.brave_search",
                "capability": "search",
                "parameters": {
                    "query": query,
                "recency_days": recency_days,
                    "max_results": max_results
                }
            }
        )


def print_section(title: str):
    """Print a section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def main():
    """Example usage of the Fabric client"""
    
    # Initialize client
    client = FabricClient()
    
    # 1. Check server health
    print_section("1. Server Health Check")
    health = client.health()
    print(json.dumps(health, indent=2))
    
    # 2. List all agents
    print_section("2. List All Agents")
    agents = client.list_agents()
    print(f"Found {len(agents['agents'])} agents:")
    for agent in agents["agents"]:
        print(f"  - {agent['agent_id']} ({agent['display_name']}) - {agent['status']}")
        print(f"    Capabilities: {', '.join(c['name'] for c in agent['capabilities'])}")
    
    # 3. List agents with a specific capability
    print_section("3. List Agents with 'reason' Capability")
    reasoning_agents = client.list_agents(capability="reason")
    print(f"Found {len(reasoning_agents['agents'])} agents with 'reason' capability:")
    for agent in reasoning_agents["agents"]:
        print(f"  - {agent['agent_id']}")
    
    # 4. Describe a specific agent
    print_section("4. Describe Agent: percy")
    try:
        percy = client.describe_agent("percy")
        print(json.dumps(percy, indent=2))
    except Exception as e:
        print(f"Error: {e}")
    
    # 5. Preview routing
    print_section("5. Preview Routing for percy.reason")
    try:
        preview = client.preview_route("percy", "reason")
        print(json.dumps(preview, indent=2))
    except Exception as e:
        print(f"Error: {e}")
    
    # 6. Call an agent (synchronous)
    print_section("6. Call Agent: percy.reason (synchronous)")
    try:
        result = client.call_agent(
            agent_id="percy",
            capability="reason",
            task="What are the key benefits of using MCP for agent communication?",
            context={
                "depth": "detailed",
                "format": "bullet_points"
            }
        )
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
    
    # 7. Call another agent
    print_section("7. Call Agent: coder.code")
    try:
        result = client.call_agent(
            agent_id="coder",
            capability="code",
            task="Write a Python function to calculate the factorial of a number using recursion",
            context={
                "language": "python",
                "include_tests": True
            }
        )
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
    
    # 8. Test error handling
    print_section("8. Test Error Handling (non-existent agent)")
    try:
        result = client.call_agent(
            agent_id="nonexistent",
            capability="test",
            task="This should fail"
        )
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
    
    # 9. List available tools
    print_section("9. List Available Tools")
    try:
        tools = client.list_tools()
        print(f"Total tools available: {tools.get('count', 0)}")
        print("\nFirst 10 tools:")
        for tool in tools.get('tools', [])[:10]:
            print(f"  - {tool['tool_id']} ({tool['provider']})")
    except Exception as e:
        print(f"Error: {e}")
    
    # 10. Calculate using built-in tool
    print_section("10. Calculate Expression (built-in tool)")
    try:
        result = client.calculate("(2 + 3) * 4 / 2")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
    
    # 11. Hash using built-in tool
    print_section("11. Generate SHA256 Hash (built-in tool)")
    try:
        result = client.hash_string("Hello, Fabric!")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
    
    # 12. Base64 encode
    print_section("12. Base64 Encode (built-in tool)")
    try:
        result = client.base64_encode("Hello, World!")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Error: {e}")
    
    # 13. Filter tools by category
    print_section("13. List Math Tools")
    try:
        tools = client.list_tools(category="math")
        print(f"Math tools: {len(tools.get('tools', []))}")
        for tool in tools.get('tools', []):
            print(f"  - {tool['tool_id']}")
    except Exception as e:
        print(f"Error: {e}")
    
    print_section("Done!")


if __name__ == "__main__":
    main()

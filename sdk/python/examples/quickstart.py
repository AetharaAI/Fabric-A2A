"""
Fabric A2A SDK - Quickstart Example
Demonstrates common usage patterns.
"""

import os
import asyncio
from fabric_a2a import FabricClient, FabricError

# Configuration
SERVER_URL = os.environ.get("FABRIC_URL", "https://fabric.perceptor.us")
API_TOKEN = os.environ.get("FABRIC_TOKEN", "your-token")


def example_basic_tool_call():
    """Example 1: Basic tool call"""
    print("=" * 60)
    print("Example 1: Basic Tool Call")
    print("=" * 60)

    client = FabricClient(base_url=SERVER_URL, token=API_TOKEN)

    try:
        # Calculate math expression
        result = client.tools.math.calculate("2 + 2")

        print(f"Status: {'Success' if result.ok else 'Failed'}")
        print(f"Response: {result.result}")
        print(f"Trace ID: {result.trace.trace_id if result.trace else 'N/A'}")

    except FabricError as e:
        print(f"Error: {e}")

    client.close()


def example_tool_list():
    """Example 2: List available tools"""
    print("\n" + "=" * 60)
    print("Example 2: List Available Tools")
    print("=" * 60)

    client = FabricClient(base_url=SERVER_URL, token=API_TOKEN)

    try:
        tools = client.tools.list()
        print(f"Found {len(tools)} tools:")
        for tool in tools[:10]:
            print(f"  - {tool['tool_id']} ({tool.get('category', 'general')})")
        if len(tools) > 10:
            print(f"  ... and {len(tools) - 10} more")

    except FabricError as e:
        print(f"Error: {e}")

    client.close()


def example_agent_discovery():
    """Example 3: Agent discovery and calling"""
    print("\n" + "=" * 60)
    print("Example 3: Agent Discovery")
    print("=" * 60)

    client = FabricClient(base_url=SERVER_URL, token=API_TOKEN)

    try:
        agents = client.agents.list()
        print(f"Found {len(agents)} agents:")

        for agent in agents:
            caps = [c.name for c in agent.capabilities]
            print(f"  - {agent.agent_id}: {agent.display_name}")
            print(f"    Status: {agent.status}")
            print(f"    Capabilities: {caps}")

        if agents:
            agent = client.agents.get(agents[0].agent_id)
            if agent:
                print(f"\nDetailed info for {agent.agent_id}:")
                print(f"  Description: {agent.description or 'N/A'}")
                print(f"  Tags: {agent.tags}")
                print(f"  Trust Tier: {agent.trust_tier}")

    except FabricError as e:
        print(f"Error: {e}")

    client.close()


def example_agent_call():
    """Example 4: Call an agent"""
    print("\n" + "=" * 60)
    print("Example 4: Calling an Agent")
    print("=" * 60)

    client = FabricClient(base_url=SERVER_URL, token=API_TOKEN)

    try:
        answer = client.agents.call_simple(
            agent_id="percy",
            capability="reason",
            task="What is 2+2?"
        )
        print(f"Simple answer: {answer}")

        result = client.agents.call(
            agent_id="percy",
            capability="reason",
            task="What is 2+2?",
            timeout_ms=30000
        )

        print(f"\nDetailed result:")
        print(f"  Status: {'Success' if result.ok else 'Failed'}")
        print(f"  Trace ID: {result.trace.trace_id if result.trace else 'N/A'}")
        if result.result:
            print(f"  Answer: {result.result.get('answer', 'N/A')}")

    except FabricError as e:
        print(f"Error: {e}")

    client.close()


def example_http_request():
    """Example 5: HTTP request tool"""
    print("\n" + "=" * 60)
    print("Example 5: HTTP Request")
    print("=" * 60)

    client = FabricClient(base_url=SERVER_URL, token=API_TOKEN)

    try:
        response = client.tools.web.http_request(
            url="https://api.github.com/",
            method="GET"
        )
        print(f"Status: {response.status_code}")
        print(f"Content preview: {response.body[:200]}...")

    except FabricError as e:
        print(f"Error: {e}")

    client.close()


def example_health_check():
    """Example 6: Health check"""
    print("\n" + "=" * 60)
    print("Example 6: Health Check")
    print("=" * 60)

    client = FabricClient(base_url=SERVER_URL, token=API_TOKEN)

    try:
        health = client.health()
        print(f"Status: {health.status}")
        print(f"Version: {health.version}")
        print(f"Is Healthy: {health.is_healthy}")

    except FabricError as e:
        print(f"Error: {e}")

    client.close()


def example_context_manager():
    """Example 7: Using context manager"""
    print("\n" + "=" * 60)
    print("Example 7: Context Manager")
    print("=" * 60)

    with FabricClient(base_url=SERVER_URL, token=API_TOKEN) as client:
        result = client.tools.math.calculate("sqrt(144)")
        print(f"Result: {result.result}")
        print("(Connection automatically closed)")


async def example_async():
    """Example 8: Async usage"""
    print("\n" + "=" * 60)
    print("Example 8: Async Usage")
    print("=" * 60)

    from fabric_a2a import AsyncFabricClient

    async with AsyncFabricClient(base_url=SERVER_URL, token=API_TOKEN) as client:
        results = await asyncio.gather(
            client.tools.math.calculate("2 + 2"),
            client.tools.math.calculate("10 * 10"),
            client.agents.list(),
            return_exceptions=True
        )

        print("Concurrent results:")
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"  [{i}] Error: {result}")
            else:
                print(f"  [{i}] Success: {result.result if hasattr(result, 'result') else result}")


def run_all_examples():
    """Run all sync examples"""
    example_basic_tool_call()
    example_tool_list()
    example_agent_discovery()
    example_http_request()
    example_health_check()
    example_context_manager()

    print("\n" + "=" * 60)
    print("All sync examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "async":
        asyncio.run(example_async())
    else:
        run_all_examples()

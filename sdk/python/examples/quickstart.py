"""
Fabric A2A SDK - Quickstart Example
Demonstrates common usage patterns.
"""

import os
import asyncio
from fabric_a2a import FabricClient, FabricError

# Configuration
SERVER_URL = os.environ.get("FABRIC_URL", "https://fabric-a2a.io/mcp")
API_KEY = os.environ.get("FABRIC_API_KEY", "your-api-key")


def example_basic_call():
    """Example 1: Basic tool call"""
    print("=" * 60)
    print("Example 1: Basic Tool Call")
    print("=" * 60)
    
    client = FabricClient(base_url=SERVER_URL, api_key=API_KEY)
    
    try:
        # Call the clock tool
        result = client.tools.call("builtin.clock")
        
        print(f"Status: {'✓ Success' if result.ok else '✗ Failed'}")
        print(f"Response: {result.result}")
        print(f"Latency: {result.metrics.latency_ms}ms")
        print(f"Trace ID: {result.trace.trace_id}")
        
    except FabricError as e:
        print(f"Error: {e.message}")
    
    client.close()


def example_error_handling():
    """Example 2: Error handling"""
    print("\n" + "=" * 60)
    print("Example 2: Error Handling")
    print("=" * 60)
    
    client = FabricClient(base_url=SERVER_URL, api_key=API_KEY)
    
    try:
        # Try to call a non-existent tool
        result = client.tools.call("nonexistent.tool")
        
        if not result.ok:
            print(f"Call failed as expected: {result.error}")
            print(f"Trace ID for debugging: {result.trace.trace_id}")
            print(f"Retriable: {result.is_retriable()}")
        
    except Exception as e:
        print(f"Exception: {type(e).__name__}: {e}")
    
    client.close()


def example_with_context():
    """Example 3: Using context"""
    print("\n" + "=" * 60)
    print("Example 3: Using Context")
    print("=" * 60)
    
    # Create context with metadata
    ctx = FabricClient.create_context(
        request_id="req-123",
        workflow="data-pipeline"
    )
    
    client = FabricClient(base_url=SERVER_URL, api_key=API_KEY)
    
    # All calls will include this context
    result = client.tools.call("builtin.clock", context=ctx)
    
    print(f"Result: {result.result}")
    print(f"Trace chain: {result.trace.get_chain()}")
    
    client.close()


def example_agent_discovery():
    """Example 4: Agent discovery and calling"""
    print("\n" + "=" * 60)
    print("Example 4: Agent Discovery")
    print("=" * 60)
    
    client = FabricClient(base_url=SERVER_URL, api_key=API_KEY)
    
    try:
        # List all available agents
        agents = client.agents.list()
        print(f"Found {len(agents)} agents:")
        
        for agent in agents:
            print(f"  • {agent.agent_id}: {agent.display_name}")
            print(f"    Status: {agent.status}")
            print(f"    Capabilities: {[c.name for c in agent.capabilities]}")
        
        # Get details about a specific agent
        if agents:
            agent = client.agents.get(agents[0].agent_id)
            print(f"\nDetailed info for {agent.agent_id}:")
            print(f"  Description: {agent.description or 'N/A'}")
            print(f"  Tags: {agent.tags}")
            
    except FabricError as e:
        print(f"Error: {e.message}")
    
    client.close()


def example_agent_call():
    """Example 5: Call an agent"""
    print("\n" + "=" * 60)
    print("Example 5: Calling an Agent")
    print("=" * 60)
    
    client = FabricClient(base_url=SERVER_URL, api_key=API_KEY)
    
    try:
        # Simple call
        answer = client.agents.call_simple(
            agent_id="percy",
            capability="reason",
            task="Explain what A2A means in 2 sentences"
        )
        print(f"Answer: {answer}")
        
        # Detailed call with full result
        result = client.agents.call(
            agent_id="percy",
            capability="reason",
            task="What is 2+2?",
            timeout_ms=30000
        )
        
        print(f"\nDetailed result:")
        print(f"  Status: {'✓' if result.ok else '✗'}")
        print(f"  Latency: {result.metrics.latency_ms}ms")
        print(f"  Answer: {result.result.get('answer', 'N/A')}")
        
    except FabricError as e:
        print(f"Error: {e.message}")
    
    client.close()


def example_context_manager():
    """Example 6: Using context manager"""
    print("\n" + "=" * 60)
    print("Example 6: Context Manager")
    print("=" * 60)
    
    with FabricClient(base_url=SERVER_URL, api_key=API_KEY) as client:
        result = client.tools.call("builtin.clock")
        print(f"Result: {result.result}")
        print("(Connection automatically closed)")


async def example_async():
    """Example 7: Async usage"""
    print("\n" + "=" * 60)
    print("Example 7: Async Usage")
    print("=" * 60)
    
    from fabric_a2a import AsyncFabricClient
    
    async with AsyncFabricClient(base_url=SERVER_URL, api_key=API_KEY) as client:
        # Make multiple concurrent calls
        results = await asyncio.gather(
            client.tools.call("builtin.clock"),
            client.tools.call("builtin.echo", {"message": "Hello"}),
            client.agents.list(),
            return_exceptions=True
        )
        
        print("Concurrent results:")
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"  [{i}] Error: {result}")
            else:
                print(f"  [{i}] Success: {result.result if hasattr(result, 'result') else result}")


def example_registry():
    """Example 8: Registry operations"""
    print("\n" + "=" * 60)
    print("Example 8: Registry Operations")
    print("=" * 60)
    
    client = FabricClient(base_url=SERVER_URL, api_key=API_KEY)
    
    try:
        # List registered agents
        agents = client.registry.list_agents()
        print(f"Registered agents: {len(agents)}")
        for agent in agents[:5]:  # Show first 5
            print(f"  • {agent.agent_id}: {agent.display_name}")
        
        # Search for specific agent
        results = client.registry.search("reason")
        print(f"\nSearch 'reason': {len(results)} results")
        for agent in results[:3]:
            print(f"  • {agent.agent_id}")
        
    except FabricError as e:
        print(f"Error: {e.message}")
    
    client.close()


def run_all_examples():
    """Run all sync examples"""
    example_basic_call()
    example_error_handling()
    example_with_context()
    example_agent_discovery()
    # Skip agent call if no agents available
    # example_agent_call()
    example_context_manager()
    example_registry()
    
    print("\n" + "=" * 60)
    print("All sync examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "async":
        # Run async examples
        asyncio.run(example_async())
    else:
        # Run sync examples
        run_all_examples()
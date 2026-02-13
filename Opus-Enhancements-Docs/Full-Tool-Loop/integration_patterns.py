"""
Example: Integrating AetherCheckpoint into an existing agent
=============================================================

This shows three integration patterns:
    1. Minimal — drop engine into existing loop (10 lines of change)
    2. Full Loop — use InfiniteExecutionLoop for new agents
    3. Production — with Postgres backend and LLM distillation
"""

import asyncio
import json

# ─────────────────────────────────────────────────────────
# Pattern 1: MINIMAL INTEGRATION (recommended to start)
# Drop into your existing tool-calling loop
# ─────────────────────────────────────────────────────────

async def minimal_integration_example():
    """
    If you already have an agent with a tool-calling loop,
    this is the fastest way to add checkpointing.
    
    You only need to add ~10 lines to your existing code.
    """
    from aether_checkpoint import CheckpointEngine, CheckpointConfig

    # Create the engine with your settings
    engine = CheckpointEngine.create_simple(
        objective="Build and deploy Docker pipeline for AetherOS",
        steps_per_episode=10,   # Your "10 working steps"
        token_budget=8000,      # Adjust based on your model's context window
    )

    # ── Your existing agent loop (simplified) ──
    # Just add the 3 marked lines

    done = False
    while not done:
        # Your existing model call
        context = engine.get_context()  # ← ADD: get context with rehydrated state
        action = await fake_model_decide(context)

        if action["type"] == "final_answer":
            done = True
            print(f"✅ Done: {action['answer']}")
            break

        # Your existing tool execution
        result = await fake_tool_execute(action["tool"], action["input"])

        engine.record_tool_call(action["tool"], action["input"], result)  # ← ADD: record

        # ← ADD: checkpoint when needed
        if engine.should_checkpoint():
            checkpoint = await engine.run_checkpoint()
            print(f"📸 Checkpoint {checkpoint.episode_number} | "
                  f"Compression: {checkpoint.metadata.get('compression_ratio', 0):.0%}")

    print(f"\n📊 Stats: {json.dumps(engine.stats, indent=2)}")


# ─────────────────────────────────────────────────────────
# Pattern 2: FULL LOOP (for new agents)
# Let InfiniteExecutionLoop handle everything
# ─────────────────────────────────────────────────────────

async def full_loop_example():
    """
    For new agents, use InfiniteExecutionLoop.
    You just provide two functions and it handles the rest.
    """
    from aether_checkpoint import InfiniteExecutionLoop
    from aether_checkpoint.loop import AgentAction

    # Define how your model makes decisions
    step_counter = {"n": 0}

    async def my_model_decider(context: str) -> AgentAction:
        """
        Replace this with your actual model call.
        The context string already includes rehydrated checkpoint state.
        """
        step_counter["n"] += 1

        # Simulate: after 25 total steps, task is done
        if step_counter["n"] >= 25:
            return AgentAction(
                tool_name="",
                tool_input={},
                is_final_answer=True,
                final_output="Docker pipeline deployed successfully!",
            )

        # Simulate: model picks a tool to use
        tools = ["create_file", "run_command", "check_status", "configure_service"]
        tool = tools[step_counter["n"] % len(tools)]

        return AgentAction(
            tool_name=tool,
            tool_input={"step": step_counter["n"]},
            reasoning=f"Executing step {step_counter['n']}",
        )

    # Define how tools get executed
    async def my_tool_executor(tool_name: str, tool_input: dict):
        """Replace this with your actual tool execution logic."""
        return {"status": "success", "tool": tool_name, "output": f"Completed {tool_name}"}

    # Create and run the loop
    loop = InfiniteExecutionLoop(
        objective="Build and deploy Docker pipeline for AetherOS agent fleet",
        model_decider=my_model_decider,
        tool_executor=my_tool_executor,
        steps_per_episode=10,
        token_budget=8000,
        verbose=True,
    )

    result = await loop.run()

    print(f"\n{'='*50}")
    print(f"✅ Complete: {result.success}")
    print(f"📊 Total steps: {result.total_steps}")
    print(f"📸 Total episodes: {result.total_episodes}")
    print(f"⏱  Total time: {result.total_time_seconds:.1f}s")
    print(f"📋 Checkpoints: {len(result.checkpoint_history)}")


# ─────────────────────────────────────────────────────────
# Pattern 3: PRODUCTION (with real backends)
# ─────────────────────────────────────────────────────────

async def production_example():
    """
    Production setup with Postgres for checkpoints and 
    LLM-powered distillation for smarter compression.
    
    Requires: pip install asyncpg
    """
    from aether_checkpoint import CheckpointEngine, CheckpointConfig
    from aether_checkpoint.backends import PostgresEpisodicBackend
    from aether_checkpoint.checkpointer import LLMDistillation

    # ── Set up Postgres backend ──
    pg_backend = PostgresEpisodicBackend(
        dsn="postgresql://aether:password@localhost:5432/aether_agents"
    )
    await pg_backend.initialize()  # Creates table if needed

    # ── Set up LLM distillation ──
    # This uses YOUR model to intelligently compress working memory
    async def my_llm_call(prompt: str) -> str:
        """
        Replace with your actual LLM call.
        Could be vLLM, OpenAI, Anthropic, or your local AetherPro Triad model.
        
        Example with your Apriel-1.5-15B-Thinker (great for distillation):
            response = await vllm_client.completions.create(
                model="apriel-1.5-15b-thinker",
                prompt=prompt,
                max_tokens=500,
            )
            return response.choices[0].text
        """
        # Placeholder - replace with real call
        return json.dumps({
            "progress_items": ["Placeholder distillation"],
            "current_state": {"status": "in_progress"},
            "next_actions": ["Continue task"],
            "dependencies": [],
            "warnings": [],
        })

    distiller = LLMDistillation(llm_callable=my_llm_call)

    # ── Create engine with production backends ──
    engine = CheckpointEngine(
        config=CheckpointConfig(
            objective="Deploy complete AetherOS fleet",
            max_steps_per_episode=10,
            max_tokens_per_episode=12000,
            adaptive_checkpointing=True,
            verbose=True,
        ),
        episodic_backend=pg_backend,
        distillation_strategy=distiller,
    )

    # Use engine in your loop (same as Pattern 1)
    print("Production engine ready!")
    print(f"Config: {engine.config}")


# ─────────────────────────────────────────────────────────
# Fake helpers for the examples above
# ─────────────────────────────────────────────────────────

_step = {"n": 0}

async def fake_model_decide(context: str) -> dict:
    """Simulates a model deciding what to do."""
    _step["n"] += 1
    if _step["n"] > 25:
        return {"type": "final_answer", "answer": "Pipeline deployed!"}
    return {
        "type": "tool_call",
        "tool": ["search", "create_file", "run_cmd", "check"][_step["n"] % 4],
        "input": {"step": _step["n"]},
    }

async def fake_tool_execute(tool: str, input_data: dict) -> dict:
    """Simulates executing a tool."""
    return {"status": "success", "tool": tool, "data": f"Result for {tool}"}


# ─────────────────────────────────────────────────────────
# Run examples
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Pattern 1: Minimal Integration")
    print("=" * 60)
    asyncio.run(minimal_integration_example())

    print("\n" + "=" * 60)
    print("Pattern 2: Full Execution Loop")
    print("=" * 60)
    asyncio.run(full_loop_example())

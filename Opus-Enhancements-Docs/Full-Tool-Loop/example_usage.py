"""
Example: How to plug the Checkpoint Engine into any agent.

This demo shows a simple simulated agent that counts to a target number
using tool calls. It demonstrates the full cycle:
  1. Active execution (tool calls)
  2. Checkpoint (distill state)
  3. Rehydrate (reset context, load checkpoint)
  4. Continue until done

Run: python example_usage.py
"""

import json
import logging
from typing import Any, Optional

from aether_checkpoint import CheckpointEngine, MemoryConfig
from aether_checkpoint.loop import LoopEvent

# Set up logging so you can see the engine working
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)


# =============================================================================
# STEP 1: Implement the AgentProtocol for your agent
# =============================================================================

class DemoAgent:
    """A simple demo agent that counts to a target using tool calls.

    Replace this with your actual agent (AetherAgent, LangChain, CrewAI, etc.)
    The only requirement is implementing these 3 methods.
    """

    def __init__(self, target: int = 35):
        self.target = target
        self._current_count = 0

    def decide_action(self, system_prompt: str, messages: list[dict]) -> dict:
        """Decide what tool to call next.

        In a real agent, this is where you'd call your LLM with the
        system prompt + messages and parse out the tool call.
        """
        # Check if we have continuation state
        for msg in messages:
            if isinstance(msg.get("content"), str) and "CONTINUATION STATE" in msg["content"]:
                # Extract current count from checkpoint
                for line in msg["content"].split("\n"):
                    if "current_count:" in line:
                        try:
                            self._current_count = int(line.split(":")[-1].strip())
                        except ValueError:
                            pass

        # Check last tool result
        for msg in reversed(messages):
            if msg.get("role") == "tool":
                try:
                    data = json.loads(msg["content"])
                    if "result" in data and isinstance(data["result"], int):
                        self._current_count = data["result"]
                except (json.JSONDecodeError, TypeError):
                    pass

        if self._current_count >= self.target:
            return {"tool": "__DONE__", "input": {}, "reasoning": f"Reached target {self.target}"}

        return {
            "tool": "increment",
            "input": {"current": self._current_count, "amount": 1},
            "reasoning": f"Count is {self._current_count}, need {self.target}",
            "tokens_used": 50,
        }

    def execute_tool(self, tool_name: str, tool_input: dict) -> Any:
        """Execute the tool call.

        In a real agent, this dispatches to your tool registry.
        """
        if tool_name == "increment":
            new_val = tool_input["current"] + tool_input["amount"]
            self._current_count = new_val
            return new_val
        raise ValueError(f"Unknown tool: {tool_name}")

    def distill_checkpoint(
        self,
        objective: str,
        working_memory_text: str,
        previous_checkpoint: Optional[str],
    ) -> dict:
        """Compress working memory into structured checkpoint.

        In a real agent, you'd call the LLM with a distillation prompt.
        Here we just extract the key state mechanically.
        """
        return {
            "objective": objective,
            "progress": [f"Counted up to {self._current_count}"],
            "state": {"current_count": self._current_count, "target": self.target},
            "next_action": f"Continue counting from {self._current_count} to {self.target}",
            "dependencies": [],
            "errors": [],
        }


# =============================================================================
# STEP 2: Configure and run
# =============================================================================

def event_handler(event: LoopEvent):
    """Optional callback to monitor execution."""
    if event.event_type == "step":
        print(f"  📍 Episode {event.episode}, Step {event.data.get('step', '?')}")
    elif event.event_type == "checkpoint":
        print(f"  💾 Checkpoint: {event.data.get('checkpoint_id', '?')} "
              f"(steps: {event.data.get('steps_taken', '?')})")
    elif event.event_type == "rehydrate":
        print(f"  🔄 Rehydrating from {event.data.get('checkpoint_id', '?')}")
    elif event.event_type == "complete":
        print(f"\n  ✅ COMPLETE! Episodes: {event.data.get('episodes')}, "
              f"Tool calls: {event.data.get('total_tool_calls')}")
    elif event.event_type == "safety_stop":
        print(f"\n  🛑 Safety stop: {event.data.get('reason')}")


def main():
    print("=" * 60)
    print("AetherCheckpoint Engine - Demo")
    print("=" * 60)
    print()

    # Configure: 5 active steps per episode + 1 checkpoint + 1 reset = 7 total
    # This means counting to 35 will take ~7 episodes
    config = MemoryConfig(
        max_steps_per_episode=5,    # 5 active tool calls per episode
        checkpoint_step=6,
        reset_step=7,
        max_total_episodes=20,      # Safety limit
        max_total_tool_calls=200,   # Safety limit
        checkpoint_dir="./demo_checkpoints",
    )

    # Create the agent
    agent = DemoAgent(target=35)

    # Create the engine
    engine = CheckpointEngine(
        agent=agent,
        config=config,
        on_event=event_handler,
    )

    # Run!
    print(f"Objective: Count to {agent.target}")
    print(f"Steps per episode: {config.max_steps_per_episode}")
    print(f"Expected episodes: ~{agent.target // config.max_steps_per_episode + 1}")
    print()

    final = engine.run(objective=f"Count to {agent.target}")

    # Show the final checkpoint
    print()
    print("=" * 60)
    print("FINAL CHECKPOINT:")
    print("=" * 60)
    print(final.to_continuation_prompt())

    # Show history
    print()
    print("=" * 60)
    print("CHECKPOINT CHAIN:")
    print("=" * 60)
    for cp in engine.get_history():
        print(f"  {cp['checkpoint_id']} | Episode {cp['episode_number']} | {cp['objective'][:50]}")

    # === BONUS: Resume from checkpoint ===
    print()
    print("=" * 60)
    print("RESUME DEMO: Simulating crash recovery...")
    print("=" * 60)

    # Create a new engine (simulating a fresh process after crash)
    agent2 = DemoAgent(target=35)
    engine2 = CheckpointEngine(
        agent=agent2,
        config=config,
        on_event=event_handler,
    )

    # Resume from the 3rd checkpoint (as if we crashed mid-execution)
    history = engine.get_history()
    if len(history) >= 3:
        resume_id = history[2]["checkpoint_id"]
        print(f"Resuming from checkpoint: {resume_id}")
        resumed_final = engine2.resume(checkpoint_id=resume_id)
        print(f"\nResumed and completed! Final state: {resumed_final.state}")


if __name__ == "__main__":
    main()

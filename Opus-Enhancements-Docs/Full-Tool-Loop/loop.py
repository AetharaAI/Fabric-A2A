"""
Execution Loop: The core runtime that implements infinite tool calling.

This is where your 10+1+1 pattern comes to life:
  - Steps 1-N:  Active work (tool calls solving the objective)
  - Step N+1:   Checkpoint (distill working memory into structured state)
  - Step N+2:   Rehydrate (clear context, load checkpoint, continue)

The loop repeats until the objective is complete or safety limits are hit.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Protocol

from .checkpoint import Checkpoint
from .config import CheckpointTrigger, MemoryConfig
from .memory import ToolResult, WorkingMemory

logger = logging.getLogger("aether_checkpoint")


# =============================================================================
# PROTOCOL: What your agent must implement to plug into this engine
# =============================================================================

class AgentProtocol(Protocol):
    """Interface your agent must satisfy to use the checkpoint engine.

    You don't need to inherit from this. Just implement these methods.
    Duck typing works fine.
    """

    def decide_action(self, system_prompt: str, messages: list[dict]) -> dict:
        """Given the current context, decide the next tool call.

        Returns a dict with:
            - "tool": str (tool name, or "__DONE__" if objective is complete)
            - "input": dict (tool arguments)
            - "reasoning": str (optional, why this action)
            - "tokens_used": int (estimated tokens in this response)
        """
        ...

    def execute_tool(self, tool_name: str, tool_input: dict) -> Any:
        """Execute a tool call and return the result."""
        ...

    def distill_checkpoint(self, objective: str, working_memory_text: str, previous_checkpoint: Optional[str]) -> dict:
        """Compress working memory into structured checkpoint state.

        This is the CRITICAL function - Step 11 (checkpoint step).

        Should return a dict with at minimum:
            - "objective": str
            - "progress": list[str]
            - "state": dict
            - "next_action": str
            - "dependencies": list[str]
            - "errors": list[str]
        """
        ...


# =============================================================================
# EXECUTION EVENTS (for observability / hooks)
# =============================================================================

@dataclass
class LoopEvent:
    """Events emitted during execution for monitoring."""
    event_type: str  # "step", "checkpoint", "rehydrate", "complete", "error", "safety_stop"
    episode: int
    step: int
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    data: dict = field(default_factory=dict)


EventCallback = Callable[[LoopEvent], None]


# =============================================================================
# THE EXECUTION LOOP
# =============================================================================

class ExecutionLoop:
    """The infinite execution engine.

    This is the runtime that converts a stateless LLM into a persistent process.

    Usage:
        loop = ExecutionLoop(
            agent=my_agent,           # Your agent (implements AgentProtocol)
            working_memory=wm,        # Layer 1
            config=MemoryConfig(...), # Tuning
        )

        final_checkpoint = loop.run(
            objective="Build and deploy the Docker pipeline",
            initial_checkpoint=None,  # Or a previous checkpoint to resume from
        )
    """

    def __init__(
        self,
        agent: AgentProtocol,
        working_memory: WorkingMemory,
        config: MemoryConfig = None,
        on_event: Optional[EventCallback] = None,
    ):
        self.agent = agent
        self.working_memory = working_memory
        self.config = config or MemoryConfig()
        self.on_event = on_event or (lambda e: None)

        # Runtime state
        self._episode = 0
        self._total_tool_calls = 0
        self._checkpoints: list[Checkpoint] = []
        self._running = False

    def run(
        self,
        objective: str,
        initial_checkpoint: Optional[Checkpoint] = None,
    ) -> Checkpoint:
        """Run the execution loop until objective is complete or limits are hit.

        This is the main entry point. Call this and the engine handles everything:
        episodic execution, checkpointing, rehydration, and safety limits.

        Args:
            objective: What the agent should accomplish
            initial_checkpoint: Optional checkpoint to resume from

        Returns:
            The final checkpoint (either completion or where it stopped)
        """
        self._running = True
        self._episode = initial_checkpoint.episode_number if initial_checkpoint else 0
        self._total_tool_calls = initial_checkpoint.total_tool_calls if initial_checkpoint else 0
        current_checkpoint = initial_checkpoint

        logger.info(f"Starting execution loop for objective: {objective}")

        try:
            while self._running:
                # === SAFETY CHECKS ===
                if self._episode >= self.config.max_total_episodes:
                    logger.warning(f"Hit max episodes limit ({self.config.max_total_episodes})")
                    self._emit("safety_stop", {"reason": "max_episodes", "episodes": self._episode})
                    break

                if self._total_tool_calls >= self.config.max_total_tool_calls:
                    logger.warning(f"Hit max tool calls limit ({self.config.max_total_tool_calls})")
                    self._emit("safety_stop", {"reason": "max_tool_calls", "total": self._total_tool_calls})
                    break

                # === RUN ONE EPISODE ===
                self._episode += 1
                logger.info(f"--- Episode {self._episode} ---")

                episode_result = self._run_episode(objective, current_checkpoint)

                if episode_result.objective_complete:
                    logger.info(f"Objective complete after {self._episode} episodes, {self._total_tool_calls} tool calls")
                    self._emit("complete", {
                        "episodes": self._episode,
                        "total_tool_calls": self._total_tool_calls,
                    })
                    self._running = False

                # The episode always produces a checkpoint (even on completion)
                current_checkpoint = episode_result.checkpoint
                self._checkpoints.append(current_checkpoint)

                if not self._running:
                    break

                # === REHYDRATE for next episode ===
                self._emit("rehydrate", {"checkpoint_id": current_checkpoint.checkpoint_id})
                self.working_memory.clear()

        except KeyboardInterrupt:
            logger.info("Execution interrupted by user")
            self._emit("safety_stop", {"reason": "user_interrupt"})
        except Exception as e:
            logger.error(f"Execution loop error: {e}")
            self._emit("error", {"error": str(e)})
            raise

        return current_checkpoint

    def stop(self):
        """Gracefully stop the loop after the current episode completes."""
        self._running = False

    # =========================================================================
    # INTERNAL: Single Episode Execution
    # =========================================================================

    @dataclass
    class _EpisodeResult:
        checkpoint: Checkpoint
        objective_complete: bool = False
        steps_taken: int = 0

    def _run_episode(
        self,
        objective: str,
        previous_checkpoint: Optional[Checkpoint],
    ) -> _EpisodeResult:
        """Execute one episode: N active steps → checkpoint → prepare for rehydration."""

        self.working_memory.clear()
        objective_complete = False
        steps_taken = 0

        # Build the system prompt with checkpoint context
        system_prompt = self._build_system_prompt(objective, previous_checkpoint)

        # Message history for this episode (starts fresh each episode)
        messages = []

        if previous_checkpoint:
            # Inject the continuation state as the first message
            messages.append({
                "role": "user",
                "content": previous_checkpoint.to_continuation_prompt(),
            })

        # === ACTIVE EXECUTION STEPS (1 through max_steps_per_episode) ===
        for step in range(1, self.config.max_steps_per_episode + 1):
            self._emit("step", {"episode": self._episode, "step": step})

            # Check adaptive triggers BEFORE each step
            if self._should_checkpoint_early(step):
                logger.info(f"Adaptive checkpoint triggered at step {step}")
                break

            # Ask the agent what to do
            action = self.agent.decide_action(system_prompt, messages)

            tool_name = action.get("tool", "")
            tool_input = action.get("input", {})
            tokens_used = action.get("tokens_used", 0)

            # Check if the agent says it's done
            if tool_name == "__DONE__":
                objective_complete = True
                logger.info(f"Agent signaled objective complete at episode {self._episode}, step {step}")
                break

            # Execute the tool
            try:
                result = self.agent.execute_tool(tool_name, tool_input)
                success = True
                error = None
            except Exception as e:
                result = f"ERROR: {e}"
                success = False
                error = str(e)
                logger.warning(f"Tool execution error: {e}")

            # Record in working memory
            tool_result = ToolResult(
                step_number=step,
                tool_name=tool_name,
                tool_input=tool_input,
                tool_output=result,
                tokens_used=tokens_used,
                success=success,
                error=error,
            )
            self.working_memory.append(tool_result)
            self._total_tool_calls += 1
            steps_taken = step

            # Update message history for the agent's next decision
            messages.append({"role": "assistant", "content": json.dumps(action, default=str)})
            messages.append({"role": "tool", "content": json.dumps({"result": result}, default=str)})

            # Error recovery checkpoint
            if not success and CheckpointTrigger.ERROR_RECOVERY in self.config.active_triggers:
                logger.info("Error recovery checkpoint triggered")
                break

        # === CHECKPOINT STEP (Step N+1) ===
        checkpoint = self._create_checkpoint(
            objective=objective,
            previous_checkpoint=previous_checkpoint,
            objective_complete=objective_complete,
        )

        self._emit("checkpoint", {
            "checkpoint_id": checkpoint.checkpoint_id,
            "episode": self._episode,
            "steps_taken": steps_taken,
            "objective_complete": objective_complete,
        })

        return self._EpisodeResult(
            checkpoint=checkpoint,
            objective_complete=objective_complete,
            steps_taken=steps_taken,
        )

    # =========================================================================
    # INTERNAL: Checkpoint Creation (Step 11 - the critical distillation)
    # =========================================================================

    def _create_checkpoint(
        self,
        objective: str,
        previous_checkpoint: Optional[Checkpoint],
        objective_complete: bool,
    ) -> Checkpoint:
        """Distill working memory into structured continuation state.

        This is Step 11 - the most important step in the entire architecture.
        """
        working_memory_text = self.working_memory.to_summary_text()
        previous_state = previous_checkpoint.to_continuation_prompt() if previous_checkpoint else None

        # Ask the agent to distill (or use a dedicated distillation model)
        distilled = self.agent.distill_checkpoint(
            objective=objective,
            working_memory_text=working_memory_text,
            previous_checkpoint=previous_state,
        )

        checkpoint = Checkpoint(
            objective=objective,
            progress=distilled.get("progress", []),
            state=distilled.get("state", {}),
            next_action=distilled.get("next_action", ""),
            dependencies=distilled.get("dependencies", []),
            errors=distilled.get("errors", []),
            episode_number=self._episode,
            total_tool_calls=self._total_tool_calls,
            parent_checkpoint_id=previous_checkpoint.checkpoint_id if previous_checkpoint else None,
            metadata={
                "objective_complete": objective_complete,
                "working_memory_token_count": self.working_memory.get_token_count(),
            },
        )

        return checkpoint

    # =========================================================================
    # INTERNAL: Adaptive Checkpoint Triggers
    # =========================================================================

    def _should_checkpoint_early(self, current_step: int) -> bool:
        """Check if any adaptive trigger wants to fire a checkpoint before the fixed step count."""

        triggers = self.config.active_triggers

        # Token threshold check
        if CheckpointTrigger.TOKEN_THRESHOLD in triggers:
            if self.working_memory.get_token_count() >= self.config.token_threshold:
                return True

        # Don't early-checkpoint on step 1 (need at least some work done)
        if current_step <= 2:
            return False

        return False

    # =========================================================================
    # INTERNAL: Prompt Construction
    # =========================================================================

    def _build_system_prompt(self, objective: str, checkpoint: Optional[Checkpoint]) -> str:
        """Build the system prompt for the agent, including checkpoint context."""

        parts = [
            "You are an autonomous agent executing a multi-step objective.",
            f"Your objective: {objective}",
            "",
            "## EXECUTION RULES",
            f"- You have {self.config.max_steps_per_episode} tool calls in this episode.",
            "- Make each tool call count. Be efficient.",
            "- When the objective is FULLY complete, return tool='__DONE__'.",
            "- If you encounter an error, try to recover or note it for the checkpoint.",
            "",
        ]

        if checkpoint:
            parts.append("## CONTINUATION FROM PREVIOUS EPISODE")
            parts.append("You are resuming from a checkpoint. Do NOT repeat completed work.")
            parts.append(f"Previous episodes completed: {checkpoint.episode_number}")
            parts.append(f"Total tool calls so far: {checkpoint.total_tool_calls}")
            parts.append("")

        parts.append("## CHECKPOINT PROTOCOL")
        parts.append(
            "At the end of this episode, your working memory will be compressed into a checkpoint. "
            "The checkpoint will contain: objective, progress, current state, next action, "
            "dependencies, and errors. This checkpoint will be used to rehydrate the next episode. "
            "Work with this in mind - make your actions produce clear, checkpointable progress."
        )

        return "\n".join(parts)

    # =========================================================================
    # INTERNAL: Event Emission
    # =========================================================================

    def _emit(self, event_type: str, data: dict = None):
        event = LoopEvent(
            event_type=event_type,
            episode=self._episode,
            step=0,
            data=data or {},
        )
        self.on_event(event)

"""
Infinite Execution Loop
========================

The highest-level abstraction. Wraps the entire checkpoint pattern
into a single async loop you can run with any agent.

This is the "just works" version for when you want to drop this
into an existing agent with minimal code changes.

Usage:
    loop = InfiniteExecutionLoop(
        objective="Build and deploy Docker pipeline",
        tool_executor=my_tool_executor,
        model_decider=my_model_call,
        steps_per_episode=10,
    )
    
    final_result = await loop.run()
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Awaitable

from .engine import CheckpointEngine, CheckpointConfig
from .memory import EpisodicMemoryBackend
from .checkpointer import DistillationStrategy

logger = logging.getLogger("aether_checkpoint.loop")


@dataclass
class LoopResult:
    """Final result when the loop completes."""
    success: bool
    final_output: Any
    total_steps: int
    total_episodes: int
    total_time_seconds: float
    checkpoint_history: list[dict]
    stats: dict


@dataclass
class AgentAction:
    """What the model decided to do."""
    tool_name: str
    tool_input: dict
    is_final_answer: bool = False
    final_output: Any = None
    reasoning: str = ""


class InfiniteExecutionLoop:
    """
    Complete infinite execution loop with checkpointing.
    
    You provide two functions:
        1. model_decider(context: str) -> AgentAction
           Given the current context, decide what tool to call
           (or return a final answer).
           
        2. tool_executor(name: str, input: dict) -> Any
           Execute a tool and return the result.
    
    The loop handles everything else:
        - Working memory management
        - Automatic checkpointing
        - Context rehydration
        - Completion detection
        - Error recovery
    """

    def __init__(
        self,
        objective: str,
        model_decider: Callable[[str], Awaitable[AgentAction]],
        tool_executor: Callable[[str, dict], Awaitable[Any]],
        steps_per_episode: int = 10,
        token_budget: int = 8000,
        max_episodes: int = 100,
        adaptive: bool = True,
        episodic_backend: Optional[EpisodicMemoryBackend] = None,
        distillation_strategy: Optional[DistillationStrategy] = None,
        on_checkpoint: Optional[Callable] = None,
        on_episode_start: Optional[Callable] = None,
        verbose: bool = True,
    ):
        self.objective = objective
        self.model_decider = model_decider
        self.tool_executor = tool_executor
        self.on_checkpoint = on_checkpoint
        self.on_episode_start = on_episode_start

        # Build engine
        config = CheckpointConfig(
            objective=objective,
            max_steps_per_episode=steps_per_episode,
            max_tokens_per_episode=token_budget,
            max_total_episodes=max_episodes,
            adaptive_checkpointing=adaptive,
            verbose=verbose,
        )
        self.engine = CheckpointEngine(
            config=config,
            episodic_backend=episodic_backend,
            distillation_strategy=distillation_strategy,
        )

    async def run(self) -> LoopResult:
        """
        Run the infinite execution loop until the objective is complete
        or max episodes are reached.
        
        This is the main entry point. Call this and let it run.
        """
        start_time = time.time()
        checkpoint_history = []

        logger.info(f"Starting infinite execution loop")
        logger.info(f"Objective: {self.objective}")
        logger.info(f"Steps per episode: {self.engine.config.max_steps_per_episode}")

        try:
            while not self.engine.is_complete:
                # Notify episode start
                if self.on_episode_start:
                    try:
                        self.on_episode_start(self.engine.stats)
                    except Exception:
                        pass

                # ── Inner execution loop (one episode) ──
                episode_step = 0
                while not self.engine.should_checkpoint() and not self.engine.is_complete:
                    # Get current context for the model
                    context = self.engine.get_context()

                    # Ask the model what to do
                    try:
                        action = await self.model_decider(context)
                    except Exception as e:
                        logger.error(f"Model decision error: {e}")
                        self.engine.record_tool_call(
                            "model_error", {}, {"error": str(e)}
                        )
                        break

                    # Check if model says we're done
                    if action.is_final_answer:
                        self.engine.mark_complete()
                        elapsed = time.time() - start_time
                        return LoopResult(
                            success=True,
                            final_output=action.final_output,
                            total_steps=self.engine.stats["total_steps"],
                            total_episodes=self.engine.stats["total_checkpoints"] + 1,
                            total_time_seconds=elapsed,
                            checkpoint_history=checkpoint_history,
                            stats=self.engine.stats,
                        )

                    # Execute the tool
                    try:
                        result = await self.tool_executor(
                            action.tool_name, action.tool_input
                        )
                    except Exception as e:
                        logger.warning(f"Tool execution error: {e}")
                        result = {"error": str(e), "tool": action.tool_name}

                    # Record the result
                    self.engine.record_tool_call(
                        action.tool_name, action.tool_input, result
                    )
                    episode_step += 1

                # ── Checkpoint cycle ──
                if not self.engine.is_complete:
                    checkpoint = await self.engine.run_checkpoint()
                    checkpoint_history.append(checkpoint.to_dict())

                    if self.on_checkpoint:
                        try:
                            self.on_checkpoint(checkpoint)
                        except Exception:
                            pass

                    # Safety: max episodes
                    if len(checkpoint_history) >= self.engine.config.max_total_episodes:
                        elapsed = time.time() - start_time
                        logger.warning("Max episodes reached — stopping")
                        return LoopResult(
                            success=False,
                            final_output="Max episodes reached",
                            total_steps=self.engine.stats["total_steps"],
                            total_episodes=len(checkpoint_history),
                            total_time_seconds=elapsed,
                            checkpoint_history=checkpoint_history,
                            stats=self.engine.stats,
                        )

        except KeyboardInterrupt:
            logger.info("Loop interrupted by user")

        elapsed = time.time() - start_time
        return LoopResult(
            success=self.engine.is_complete,
            final_output=None,
            total_steps=self.engine.stats["total_steps"],
            total_episodes=self.engine.stats["total_checkpoints"],
            total_time_seconds=elapsed,
            checkpoint_history=checkpoint_history,
            stats=self.engine.stats,
        )

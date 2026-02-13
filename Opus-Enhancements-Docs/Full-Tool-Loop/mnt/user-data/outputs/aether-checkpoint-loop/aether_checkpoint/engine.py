"""
Checkpoint Engine — The main orchestrator
==========================================

This ties together Working Memory, Episodic Memory, and the Checkpointer
into a single clean interface you can drop into any agent.

Usage:
    engine = CheckpointEngine(config)
    engine.record_tool_call("search", {"q": "test"}, {"results": [...]})
    
    if engine.should_checkpoint():
        await engine.run_checkpoint()
        # Context is now fresh — loop continues
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .memory import WorkingMemory, EpisodicMemory, EpisodeCheckpoint, EpisodicMemoryBackend
from .checkpointer import (
    Checkpointer,
    DistillationStrategy,
    RuleBasedDistillation,
    LLMDistillation,
)

logger = logging.getLogger("aether_checkpoint")


@dataclass
class CheckpointConfig:
    """
    Configuration for the checkpoint engine.
    
    The key numbers to tune:
        - max_steps_per_episode: Your "10" from the original idea.
          How many tool calls before forcing a checkpoint.
          
        - max_tokens_per_episode: Token budget for working memory.
          Set this based on your model's context window.
          Rule of thumb: (context_window * 0.4) to leave room for
          system prompt + rehydration state + model reasoning.
          
        - adaptive_checkpointing: When True, checkpoint triggers are
          smart (token threshold, subtask completion, errors).
          When False, checkpoint fires every N steps (your original idea).
    """
    # Episode sizing
    max_steps_per_episode: int = 10
    max_tokens_per_episode: int = 8000
    
    # Adaptive checkpointing thresholds
    adaptive_checkpointing: bool = True
    token_pressure_threshold: float = 0.75  # checkpoint when 75% of budget used
    
    # Objective tracking
    objective: str = ""
    
    # Maximum total episodes before hard stop (safety valve)
    max_total_episodes: int = 100
    
    # Logging
    verbose: bool = False


class CheckpointEngine:
    """
    The main engine. Drop this into any agent's tool-calling loop.
    
    It manages the full lifecycle:
        record → should_checkpoint? → checkpoint → rehydrate → continue
    
    Minimal integration example:
    
        engine = CheckpointEngine(
            config=CheckpointConfig(
                objective="Deploy Docker pipeline",
                max_steps_per_episode=10,
            )
        )
        
        while not done:
            action = model.decide(engine.get_context())
            result = execute_tool(action)
            engine.record_tool_call(action.name, action.input, result)
            
            if engine.should_checkpoint():
                checkpoint = await engine.run_checkpoint()
                # engine.get_context() now returns fresh rehydrated state
    """

    def __init__(
        self,
        config: Optional[CheckpointConfig] = None,
        episodic_backend: Optional[EpisodicMemoryBackend] = None,
        distillation_strategy: Optional[DistillationStrategy] = None,
    ):
        self.config = config or CheckpointConfig()
        
        # Initialize memory layers
        self.working_memory = WorkingMemory(
            max_token_budget=self.config.max_tokens_per_episode
        )
        self.episodic_memory = EpisodicMemory(backend=episodic_backend)
        
        # Initialize checkpointer
        self.checkpointer = Checkpointer(
            episodic_memory=self.episodic_memory,
            strategy=distillation_strategy or RuleBasedDistillation(),
        )
        
        # State tracking
        self._current_checkpoint: Optional[EpisodeCheckpoint] = None
        self._objective_complete = False
        self._total_steps = 0
        self._total_checkpoints = 0
        
        # Custom checkpoint triggers
        self._custom_triggers: list[Callable[["CheckpointEngine"], bool]] = []

        if self.config.verbose:
            logger.setLevel(logging.DEBUG)

    # ──────────────────────────────────────────
    # Recording tool calls
    # ──────────────────────────────────────────

    def record_tool_call(
        self,
        tool_name: str,
        tool_input: dict,
        tool_output: Any,
    ) -> None:
        """Record a tool call result into working memory."""
        self.working_memory.append(tool_name, tool_input, tool_output)
        self._total_steps += 1
        
        if self.config.verbose:
            logger.debug(
                f"Step {self._total_steps} | Episode step {self.working_memory.step_count} | "
                f"~{self.working_memory.token_count} tokens | {tool_name}"
            )

    # ──────────────────────────────────────────
    # Checkpoint triggers
    # ──────────────────────────────────────────

    def should_checkpoint(self) -> bool:
        """
        Determine if it's time to checkpoint.
        
        Adaptive mode triggers on:
            - Step count reaching max_steps_per_episode
            - Token budget reaching pressure threshold
            - Any custom trigger firing
            
        Fixed mode triggers only on step count.
        """
        if self._objective_complete:
            return False

        steps = self.working_memory.step_count

        # Fixed mode: checkpoint every N steps (your original "12" idea)
        if not self.config.adaptive_checkpointing:
            return steps >= self.config.max_steps_per_episode

        # Adaptive mode: multiple triggers
        triggers = []

        # Step count trigger
        if steps >= self.config.max_steps_per_episode:
            triggers.append("max_steps")

        # Token pressure trigger
        token_ratio = (
            self.working_memory.token_count / self.config.max_tokens_per_episode
        )
        if token_ratio >= self.config.token_pressure_threshold:
            triggers.append(f"token_pressure ({token_ratio:.0%})")

        # Custom triggers
        for trigger_fn in self._custom_triggers:
            try:
                if trigger_fn(self):
                    triggers.append("custom_trigger")
            except Exception as e:
                logger.warning(f"Custom trigger error: {e}")

        if triggers and self.config.verbose:
            logger.info(f"Checkpoint triggered by: {', '.join(triggers)}")

        return len(triggers) > 0

    def add_checkpoint_trigger(self, trigger_fn: Callable[["CheckpointEngine"], bool]) -> None:
        """
        Add a custom checkpoint trigger.
        
        Example:
            # Checkpoint whenever an error occurs
            engine.add_checkpoint_trigger(
                lambda e: any("error" in str(r.tool_output).lower() 
                             for r in e.working_memory.entries[-1:])
            )
        """
        self._custom_triggers.append(trigger_fn)

    # ──────────────────────────────────────────
    # Checkpoint + Rehydrate cycle
    # ──────────────────────────────────────────

    async def run_checkpoint(self) -> EpisodeCheckpoint:
        """
        Execute the full checkpoint cycle:
            Step N+1: Distill and persist working memory
            Step N+2: Clear working memory, load rehydrated state
            
        After this call, get_context() returns fresh minimal state.
        """
        if not self.config.objective:
            raise ValueError(
                "Cannot checkpoint without an objective. "
                "Set config.objective before running."
            )

        if self.config.verbose:
            logger.info(
                f"═══ CHECKPOINT {self._total_checkpoints + 1} ═══ "
                f"Distilling {self.working_memory.step_count} steps, "
                f"~{self.working_memory.token_count} tokens"
            )

        # Step N+1: Distill and persist
        checkpoint = await self.checkpointer.checkpoint(
            working_memory=self.working_memory,
            objective=self.config.objective,
        )

        # Step N+2: Clear and rehydrate
        self.working_memory.clear()
        self._current_checkpoint = checkpoint
        self._total_checkpoints += 1

        if self.config.verbose:
            cr = checkpoint.metadata.get("compression_ratio", 0)
            logger.info(
                f"═══ REHYDRATED ═══ "
                f"Compression: {cr:.0%} | "
                f"Episode {checkpoint.episode_number}"
            )

        # Safety check: max episodes
        if self._total_checkpoints >= self.config.max_total_episodes:
            logger.warning(
                f"Reached max episodes ({self.config.max_total_episodes}). "
                f"Consider increasing or reviewing objective."
            )

        return checkpoint

    # ──────────────────────────────────────────
    # Context generation for the model
    # ──────────────────────────────────────────

    def get_context(self) -> str:
        """
        Generate the context string to inject into the model's prompt.
        
        Returns either:
            - Rehydrated checkpoint state + any new working memory
            - Just working memory if no checkpoint exists yet
            
        This is what you feed to the model on every turn.
        """
        parts = []

        # Rehydrated state from last checkpoint
        if self._current_checkpoint:
            parts.append("=== CONTINUATION STATE ===")
            parts.append(self._current_checkpoint.to_rehydration_prompt())
            parts.append("")

        # Current working memory
        if self.working_memory.step_count > 0:
            parts.append(self.working_memory.to_context_string())

        if not parts:
            return f"OBJECTIVE: {self.config.objective}\n\nNo previous state. Begin execution."

        return "\n".join(parts)

    # ──────────────────────────────────────────
    # Objective management
    # ──────────────────────────────────────────

    def mark_complete(self) -> None:
        """Mark the current objective as complete."""
        self._objective_complete = True
        if self.config.verbose:
            logger.info(
                f"Objective complete after {self._total_steps} total steps, "
                f"{self._total_checkpoints} checkpoints"
            )

    @property
    def is_complete(self) -> bool:
        return self._objective_complete

    @property
    def stats(self) -> dict:
        """Get execution statistics."""
        return {
            "total_steps": self._total_steps,
            "total_checkpoints": self._total_checkpoints,
            "current_episode_steps": self.working_memory.step_count,
            "current_episode_tokens": self.working_memory.token_count,
            "objective": self.config.objective,
            "is_complete": self._objective_complete,
        }

    # ──────────────────────────────────────────
    # Convenience factory methods
    # ──────────────────────────────────────────

    @classmethod
    def create_with_llm_distillation(
        cls,
        llm_callable: Callable,
        config: Optional[CheckpointConfig] = None,
        episodic_backend: Optional[EpisodicMemoryBackend] = None,
    ) -> "CheckpointEngine":
        """
        Factory: create engine with LLM-powered distillation.
        
        Args:
            llm_callable: async function(prompt: str) -> str
        """
        return cls(
            config=config,
            episodic_backend=episodic_backend,
            distillation_strategy=LLMDistillation(llm_callable=llm_callable),
        )

    @classmethod
    def create_simple(
        cls,
        objective: str,
        steps_per_episode: int = 10,
        token_budget: int = 8000,
    ) -> "CheckpointEngine":
        """
        Factory: create a simple engine with defaults.
        Good for quick integration and testing.
        """
        return cls(
            config=CheckpointConfig(
                objective=objective,
                max_steps_per_episode=steps_per_episode,
                max_tokens_per_episode=token_budget,
                verbose=True,
            )
        )

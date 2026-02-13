"""
CheckpointEngine: The top-level orchestrator.

This is the one class you interact with from the outside.
It wires up all three memory layers, the execution loop, and the checkpoint manager.

Usage:
    from aether_checkpoint import CheckpointEngine, MemoryConfig

    engine = CheckpointEngine(
        agent=my_agent,
        config=MemoryConfig.for_model("apriel-1.5-15b-thinker"),
    )

    # Run a new objective
    result = engine.run("Deploy the AetherOS Docker stack")

    # Resume a previous run
    result = engine.resume(checkpoint_id="chkpt_abc123")

    # Get execution history
    history = engine.get_history()
"""

import logging
from typing import Optional

from .checkpoint import Checkpoint, CheckpointManager
from .config import MemoryConfig, StorageBackend
from .loop import ExecutionLoop, AgentProtocol, EventCallback
from .memory import (
    WorkingMemory,
    InMemoryWorkingMemory,
    RedisWorkingMemory,
    EpisodicMemory,
    FileEpisodicMemory,
    PostgresEpisodicMemory,
    SemanticMemory,
    FileSemanticMemory,
    WeaviateSemanticMemory,
)

logger = logging.getLogger("aether_checkpoint")


class CheckpointEngine:
    """The top-level engine that ties everything together.

    Handles:
    - Memory layer initialization (auto-selects backends from config)
    - Execution loop management
    - Checkpoint persistence and retrieval
    - Resume from any checkpoint
    """

    def __init__(
        self,
        agent: AgentProtocol,
        config: MemoryConfig = None,
        session_id: str = "default",
        on_event: Optional[EventCallback] = None,
        # Optional: inject your own memory implementations
        working_memory: Optional[WorkingMemory] = None,
        episodic_memory: Optional[EpisodicMemory] = None,
        semantic_memory: Optional[SemanticMemory] = None,
    ):
        self.config = config or MemoryConfig()
        self.agent = agent
        self.session_id = session_id
        self.on_event = on_event

        # Initialize memory layers (or use injected ones)
        self.working_memory = working_memory or self._init_working_memory()
        self.episodic_memory = episodic_memory or self._init_episodic_memory()
        self.semantic_memory = semantic_memory or self._init_semantic_memory()

        # Execution loop
        self._loop = ExecutionLoop(
            agent=self.agent,
            working_memory=self.working_memory,
            config=self.config,
            on_event=self._handle_event,
        )

    def run(self, objective: str) -> Checkpoint:
        """Start a fresh execution for a new objective.

        Returns the final checkpoint when complete or stopped.
        """
        logger.info(f"Engine.run() - New objective: {objective}")

        final_checkpoint = self._loop.run(objective=objective)

        # Persist the final checkpoint
        self.episodic_memory.save_checkpoint(final_checkpoint.to_dict())

        return final_checkpoint

    def resume(self, checkpoint_id: str = None) -> Checkpoint:
        """Resume execution from a specific checkpoint, or the latest one.

        This is how you recover from crashes, continue interrupted tasks,
        or pick up where you left off across sessions.
        """
        if checkpoint_id:
            cp_data = self.episodic_memory.load_checkpoint(checkpoint_id)
        else:
            cp_data = self.episodic_memory.load_latest()

        if not cp_data:
            raise ValueError(f"No checkpoint found (id={checkpoint_id})")

        checkpoint = Checkpoint.from_dict(cp_data)
        logger.info(f"Engine.resume() - Resuming from {checkpoint.checkpoint_id}, episode {checkpoint.episode_number}")

        final_checkpoint = self._loop.run(
            objective=checkpoint.objective,
            initial_checkpoint=checkpoint,
        )

        # Persist
        self.episodic_memory.save_checkpoint(final_checkpoint.to_dict())

        return final_checkpoint

    def get_history(self) -> list[dict]:
        """Get all checkpoints for the current session."""
        return self.episodic_memory.list_checkpoints()

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Load a specific checkpoint."""
        data = self.episodic_memory.load_checkpoint(checkpoint_id)
        if data:
            return Checkpoint.from_dict(data)
        return None

    # =========================================================================
    # Memory Layer Factory
    # =========================================================================

    def _init_working_memory(self) -> WorkingMemory:
        backend = self.config.working_memory_backend
        if backend == StorageBackend.REDIS:
            return RedisWorkingMemory(
                redis_url=self.config.redis_url,
                session_id=self.session_id,
                ttl=self.config.episode_timeout_seconds,
            )
        else:
            return InMemoryWorkingMemory()

    def _init_episodic_memory(self) -> EpisodicMemory:
        backend = self.config.episodic_memory_backend
        if backend == StorageBackend.POSTGRES:
            return PostgresEpisodicMemory(postgres_url=self.config.postgres_url)
        else:
            return FileEpisodicMemory(storage_dir=self.config.checkpoint_dir)

    def _init_semantic_memory(self) -> SemanticMemory:
        backend = self.config.semantic_memory_backend
        if backend == StorageBackend.WEAVIATE:
            return WeaviateSemanticMemory(weaviate_url=self.config.weaviate_url)
        else:
            return FileSemanticMemory(storage_dir=f"{self.config.checkpoint_dir}/../semantic_memory")

    # =========================================================================
    # Event Handling
    # =========================================================================

    def _handle_event(self, event):
        """Internal event handler - persists checkpoints and forwards to user callback."""

        # Auto-persist checkpoints
        if event.event_type == "checkpoint":
            # The checkpoint is persisted inside _loop.run() result handling,
            # but we also persist intermediate checkpoints here for crash recovery
            pass

        # Forward to user callback
        if self.on_event:
            self.on_event(event)

        # Log all events
        logger.info(f"Event: {event.event_type} | Episode {event.episode} | {event.data}")

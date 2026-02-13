"""
Configuration for the Checkpoint Engine.
All tunables live here so you can adapt to any model, any context window, any backend.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CheckpointTrigger(Enum):
    """When to fire a checkpoint. Your original idea was FIXED_STEP (every N steps).
    The adaptive triggers below make it intelligent."""

    FIXED_STEP = "fixed_step"              # Every N steps (your original 10+1+1 pattern)
    TOKEN_THRESHOLD = "token_threshold"    # When token count exceeds limit
    SUBTASK_COMPLETE = "subtask_complete"  # When a subtask finishes
    OBJECTIVE_CHANGE = "objective_change"  # When the goal shifts
    ERROR_RECOVERY = "error_recovery"      # After an error, checkpoint before retry
    UNCERTAINTY_HIGH = "uncertainty_high"  # Model confidence drops


class StorageBackend(Enum):
    """Which storage backends to use. Start with FILE for simplicity,
    graduate to REDIS/POSTGRES/WEAVIATE for production."""

    FILE = "file"           # JSON files on disk - great for development
    REDIS = "redis"         # Working memory in production
    POSTGRES = "postgres"   # Episodic memory in production
    WEAVIATE = "weaviate"   # Semantic memory in production


@dataclass
class MemoryConfig:
    """Master configuration. Adjust these based on your model's context window."""

    # === EXECUTION LOOP SETTINGS ===
    # Your original insight: set based on model context window
    max_steps_per_episode: int = 10        # Active work steps (your "10")
    checkpoint_step: int = 11              # Save state (your "11th")
    reset_step: int = 12                   # Rehydrate (your "12th")

    # === ADAPTIVE CHECKPOINT TRIGGERS ===
    # Which triggers are active (can combine multiple)
    active_triggers: list[CheckpointTrigger] = field(default_factory=lambda: [
        CheckpointTrigger.FIXED_STEP,
        CheckpointTrigger.TOKEN_THRESHOLD,
        CheckpointTrigger.SUBTASK_COMPLETE,
        CheckpointTrigger.ERROR_RECOVERY,
    ])

    # Token threshold for adaptive checkpointing
    # Rule of thumb: set to ~60% of your model's context window
    token_threshold: int = 12_000          # For a 20K context model
    token_counter_model: str = "cl100k_base"  # tiktoken encoding name

    # === CONTEXT BUDGET ===
    # How much space the rehydrated checkpoint gets in the new loop
    max_checkpoint_tokens: int = 500       # Distilled state must fit in this
    max_working_memory_tokens: int = 8_000 # Total working memory budget

    # === STORAGE BACKENDS ===
    working_memory_backend: StorageBackend = StorageBackend.FILE
    episodic_memory_backend: StorageBackend = StorageBackend.FILE
    semantic_memory_backend: StorageBackend = StorageBackend.FILE

    # === CONNECTION STRINGS (for production backends) ===
    redis_url: Optional[str] = "redis://localhost:6379/0"
    postgres_url: Optional[str] = "postgresql://localhost:5432/aether_checkpoints"
    weaviate_url: Optional[str] = "http://localhost:8080"

    # === FILE BACKEND PATHS (for development) ===
    checkpoint_dir: str = "./checkpoints"
    working_memory_dir: str = "./working_memory"

    # === DISTILLATION SETTINGS ===
    # The prompt template used to compress working memory into a checkpoint
    distillation_model: Optional[str] = None  # If None, uses the same model as the agent
    distillation_max_tokens: int = 400

    # === SAFETY ===
    max_total_episodes: int = 100          # Hard cap to prevent runaway agents
    max_total_tool_calls: int = 1_000      # Absolute ceiling
    episode_timeout_seconds: int = 300     # 5 min per episode max

    def effective_loop_size(self) -> int:
        """Total steps per episode including checkpoint + reset."""
        return self.reset_step

    @classmethod
    def for_model(cls, model_name: str) -> "MemoryConfig":
        """Factory: auto-configure based on known model context windows.

        This is your insight about 'the number comes from the model you're using.'
        """
        # Context windows for common models (tokens)
        MODEL_CONTEXTS = {
            "apriel-1.5-15b-thinker": 32_768,
            "kimi-k2": 131_072,
            "minimax-m2": 65_536,
            "llama-3.1-8b": 131_072,
            "llama-3.1-70b": 131_072,
            "mistral-7b": 32_768,
            "qwen2.5-72b": 131_072,
            "gpt-4o": 128_000,
            "claude-sonnet-4-5": 200_000,
        }

        ctx = MODEL_CONTEXTS.get(model_name, 32_768)

        # Your formula: usable context = context_window * 0.6
        # Then: max_steps = usable_tokens / avg_tokens_per_step
        # Assume ~800 tokens per tool call round-trip
        usable = int(ctx * 0.6)
        avg_per_step = 800
        active_steps = max(5, min(usable // avg_per_step, 50))

        return cls(
            max_steps_per_episode=active_steps,
            checkpoint_step=active_steps + 1,
            reset_step=active_steps + 2,
            token_threshold=usable,
            max_working_memory_tokens=usable,
            max_checkpoint_tokens=min(1000, usable // 10),
        )

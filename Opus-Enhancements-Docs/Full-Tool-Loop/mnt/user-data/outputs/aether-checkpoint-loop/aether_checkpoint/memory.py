"""
Memory Layer System
===================

Three-tier memory architecture mapping to your existing stack:
    - Working Memory  → Redis (fast, ephemeral)
    - Episodic Memory → PostgreSQL (structured checkpoints)
    - Semantic Memory  → Weaviate (embeddings, long-term knowledge)

Each layer has a simple interface so you can swap backends easily.
"""

from __future__ import annotations

import json
import time
import uuid
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from enum import Enum


class MemoryLayer(str, Enum):
    """The three tiers of agent memory."""
    WORKING = "working"      # Current loop — RAM
    EPISODIC = "episodic"    # Checkpoint summaries — Disk
    SEMANTIC = "semantic"    # Long-term knowledge — Deep storage


# ─────────────────────────────────────────────────────────
# Working Memory — Current episode only (ephemeral)
# ─────────────────────────────────────────────────────────

@dataclass
class ToolResult:
    """A single tool call and its result within the current episode."""
    step_number: int
    tool_name: str
    tool_input: dict
    tool_output: Any
    timestamp: float = field(default_factory=time.time)
    token_estimate: int = 0  # rough token count for this entry

    def to_dict(self) -> dict:
        return asdict(self)

    def to_compact(self) -> str:
        """Compact string representation for context injection."""
        return (
            f"[Step {self.step_number}] {self.tool_name}: "
            f"{json.dumps(self.tool_output, default=str)[:500]}"
        )


class WorkingMemory:
    """
    Ephemeral working memory for the current execution episode.
    
    This is your CPU cache / RAM equivalent.
    Gets cleared on every checkpoint cycle.
    """

    def __init__(self, max_token_budget: int = 8000):
        self.entries: list[ToolResult] = []
        self.max_token_budget = max_token_budget
        self._current_tokens = 0
        self.episode_id = str(uuid.uuid4())[:8]

    @property
    def step_count(self) -> int:
        return len(self.entries)

    @property
    def token_count(self) -> int:
        return self._current_tokens

    @property
    def is_approaching_limit(self) -> bool:
        """True when we've used 80%+ of token budget."""
        return self._current_tokens >= (self.max_token_budget * 0.8)

    def append(self, tool_name: str, tool_input: dict, tool_output: Any) -> ToolResult:
        """Record a tool call result."""
        # Rough token estimation: ~4 chars per token
        output_str = json.dumps(tool_output, default=str)
        token_est = (len(output_str) + len(tool_name) + len(json.dumps(tool_input))) // 4

        entry = ToolResult(
            step_number=self.step_count + 1,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            token_estimate=token_est,
        )
        self.entries.append(entry)
        self._current_tokens += token_est
        return entry

    def to_context_string(self) -> str:
        """Render working memory as a context string for the model."""
        if not self.entries:
            return "[Working memory is empty — fresh episode]"
        lines = [f"=== Working Memory (Episode {self.episode_id}) ==="]
        for entry in self.entries:
            lines.append(entry.to_compact())
        lines.append(f"=== {self.step_count} steps | ~{self._current_tokens} tokens ===")
        return "\n".join(lines)

    def clear(self) -> list[ToolResult]:
        """Clear working memory and return the entries that were cleared."""
        cleared = self.entries.copy()
        self.entries = []
        self._current_tokens = 0
        self.episode_id = str(uuid.uuid4())[:8]
        return cleared

    def get_summary_for_distillation(self) -> dict:
        """Extract key info the checkpointer needs to create a compressed state."""
        return {
            "episode_id": self.episode_id,
            "step_count": self.step_count,
            "token_count": self._current_tokens,
            "tools_used": [e.tool_name for e in self.entries],
            "entries": [e.to_dict() for e in self.entries],
        }


# ─────────────────────────────────────────────────────────
# Episodic Memory — Persistent checkpoint storage
# ─────────────────────────────────────────────────────────

@dataclass
class EpisodeCheckpoint:
    """A compressed checkpoint of one completed execution episode."""
    checkpoint_id: str
    episode_number: int
    objective: str
    progress_summary: str
    current_state: dict
    next_actions: list[str]
    dependencies: list[str]
    key_results: list[str]
    timestamp: float = field(default_factory=time.time)
    token_count: int = 0  # tokens in the original working memory
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_rehydration_prompt(self) -> str:
        """
        Generate the minimal continuation prompt for the next episode.
        
        This is THE critical function — it's what makes infinite execution work.
        Instead of feeding 10,000 tokens of history, you feed ~200 tokens of
        distilled state.
        """
        sections = [
            f"OBJECTIVE: {self.objective}",
            "",
            f"PROGRESS (after {self.episode_number} episodes):",
        ]
        for item in self.key_results:
            sections.append(f"  ✓ {item}")
        sections.append("")
        sections.append("CURRENT STATE:")
        for key, val in self.current_state.items():
            sections.append(f"  {key}: {val}")
        sections.append("")
        sections.append("NEXT ACTIONS:")
        for action in self.next_actions:
            sections.append(f"  → {action}")
        if self.dependencies:
            sections.append("")
            sections.append("DEPENDENCIES:")
            for dep in self.dependencies:
                sections.append(f"  • {dep}")
        sections.append("")
        sections.append(f"CHECKPOINT: {self.checkpoint_id} | Episode {self.episode_number}")
        return "\n".join(sections)


class EpisodicMemoryBackend(ABC):
    """Abstract backend for storing checkpoints. Implement for your storage layer."""

    @abstractmethod
    async def save_checkpoint(self, checkpoint: EpisodeCheckpoint) -> str:
        """Save checkpoint, return checkpoint_id."""
        ...

    @abstractmethod
    async def load_checkpoint(self, checkpoint_id: str) -> Optional[EpisodeCheckpoint]:
        """Load a specific checkpoint by ID."""
        ...

    @abstractmethod
    async def load_latest(self, objective_hash: str) -> Optional[EpisodeCheckpoint]:
        """Load the most recent checkpoint for a given objective."""
        ...

    @abstractmethod
    async def list_checkpoints(self, objective_hash: str, limit: int = 20) -> list[EpisodeCheckpoint]:
        """List checkpoints for an objective, newest first."""
        ...


class InMemoryEpisodicBackend(EpisodicMemoryBackend):
    """
    Simple in-memory backend for development and testing.
    
    For production, swap this out with PostgresEpisodicBackend or 
    RedisEpisodicBackend from your existing stack.
    """

    def __init__(self):
        self._store: dict[str, EpisodeCheckpoint] = {}
        self._by_objective: dict[str, list[str]] = {}

    async def save_checkpoint(self, checkpoint: EpisodeCheckpoint) -> str:
        self._store[checkpoint.checkpoint_id] = checkpoint
        obj_hash = hashlib.sha256(checkpoint.objective.encode()).hexdigest()[:12]
        if obj_hash not in self._by_objective:
            self._by_objective[obj_hash] = []
        self._by_objective[obj_hash].append(checkpoint.checkpoint_id)
        return checkpoint.checkpoint_id

    async def load_checkpoint(self, checkpoint_id: str) -> Optional[EpisodeCheckpoint]:
        return self._store.get(checkpoint_id)

    async def load_latest(self, objective_hash: str) -> Optional[EpisodeCheckpoint]:
        ids = self._by_objective.get(objective_hash, [])
        if not ids:
            return None
        return self._store.get(ids[-1])

    async def list_checkpoints(self, objective_hash: str, limit: int = 20) -> list[EpisodeCheckpoint]:
        ids = self._by_objective.get(objective_hash, [])
        return [self._store[cid] for cid in reversed(ids[-limit:])]


class EpisodicMemory:
    """
    Episodic memory manager — your Postgres/disk layer.
    
    Stores compressed checkpoint summaries across execution episodes.
    This is what gives your agent continuity across loop resets.
    """

    def __init__(self, backend: Optional[EpisodicMemoryBackend] = None):
        self.backend = backend or InMemoryEpisodicBackend()
        self._episode_counter = 0

    @property
    def episode_count(self) -> int:
        return self._episode_counter

    async def create_checkpoint(
        self,
        objective: str,
        progress_summary: str,
        current_state: dict,
        next_actions: list[str],
        key_results: list[str],
        dependencies: list[str] = None,
        metadata: dict = None,
    ) -> EpisodeCheckpoint:
        """Create and persist a new checkpoint."""
        self._episode_counter += 1
        checkpoint = EpisodeCheckpoint(
            checkpoint_id=f"chkpt_{uuid.uuid4().hex[:8]}",
            episode_number=self._episode_counter,
            objective=objective,
            progress_summary=progress_summary,
            current_state=current_state,
            next_actions=next_actions,
            key_results=key_results,
            dependencies=dependencies or [],
            metadata=metadata or {},
        )
        await self.backend.save_checkpoint(checkpoint)
        return checkpoint

    async def get_latest(self, objective: str) -> Optional[EpisodeCheckpoint]:
        """Get the most recent checkpoint for an objective."""
        obj_hash = hashlib.sha256(objective.encode()).hexdigest()[:12]
        return await self.backend.load_latest(obj_hash)

    async def get_full_history(self, objective: str, limit: int = 20) -> list[EpisodeCheckpoint]:
        """Get checkpoint history for review or debugging."""
        obj_hash = hashlib.sha256(objective.encode()).hexdigest()[:12]
        return await self.backend.list_checkpoints(obj_hash, limit)

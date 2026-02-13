"""
Checkpoint: Structured continuation state.

This is the KEY insight from the architecture:
  - Logs are archaeology (looking backward)
  - State is navigation (looking forward)

A checkpoint is NOT a dump of previous outputs.
It IS a compressed, structured description of where the agent is
and what it needs to do next.
"""

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional
from pathlib import Path


@dataclass
class Checkpoint:
    """Structured continuation memory.

    This is what Step 11 produces. It's the 'distilled state'
    that gets loaded back in Step 12 to rehydrate the agent.
    """

    # Identity
    checkpoint_id: str = field(default_factory=lambda: f"chkpt_{uuid.uuid4().hex[:8]}")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # What are we trying to accomplish?
    objective: str = ""

    # What has been done so far?
    progress: list[str] = field(default_factory=list)

    # What is the current state of things?
    state: dict[str, Any] = field(default_factory=dict)

    # What should happen next?
    next_action: str = ""

    # What does the next action depend on?
    dependencies: list[str] = field(default_factory=list)

    # Any errors or blockers encountered?
    errors: list[str] = field(default_factory=list)

    # Which episode produced this checkpoint?
    episode_number: int = 0

    # How many total tool calls have been made across all episodes?
    total_tool_calls: int = 0

    # Metadata for debugging and analytics
    metadata: dict[str, Any] = field(default_factory=dict)

    # Chain: ID of the previous checkpoint (linked list of episodes)
    parent_checkpoint_id: Optional[str] = None

    def to_continuation_prompt(self) -> str:
        """Convert checkpoint to a minimal prompt for the next episode.

        This is the rehydration payload - what the agent sees when it
        wakes up in a fresh context window.
        """
        sections = []

        sections.append(f"## CONTINUATION STATE (Checkpoint: {self.checkpoint_id})")
        sections.append(f"**Episode:** {self.episode_number + 1} (continuing from {self.episode_number})")
        sections.append(f"**Total tool calls so far:** {self.total_tool_calls}")
        sections.append(f"\n### OBJECTIVE\n{self.objective}")

        if self.progress:
            progress_str = "\n".join(f"  ✓ {p}" for p in self.progress)
            sections.append(f"\n### COMPLETED\n{progress_str}")

        if self.state:
            state_str = "\n".join(f"  - {k}: {v}" for k, v in self.state.items())
            sections.append(f"\n### CURRENT STATE\n{state_str}")

        if self.errors:
            error_str = "\n".join(f"  ⚠ {e}" for e in self.errors)
            sections.append(f"\n### ERRORS/BLOCKERS\n{error_str}")

        sections.append(f"\n### NEXT ACTION\n{self.next_action}")

        if self.dependencies:
            dep_str = "\n".join(f"  - {d}" for d in self.dependencies)
            sections.append(f"\n### DEPENDENCIES\n{dep_str}")

        sections.append("\n---")
        sections.append("Resume execution from NEXT ACTION. Do not repeat completed work.")

        return "\n".join(sections)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_dict(cls, data: dict) -> "Checkpoint":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_json(cls, raw: str) -> "Checkpoint":
        return cls.from_dict(json.loads(raw))


class CheckpointManager:
    """Handles persisting and loading checkpoints.

    Supports file-based storage for development and can be extended
    to Postgres for production (see memory.py for EpisodicMemory).
    """

    def __init__(self, storage_dir: str = "./checkpoints"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._chain: list[str] = []  # Ordered list of checkpoint IDs

    def save(self, checkpoint: Checkpoint) -> str:
        """Persist a checkpoint. Returns the checkpoint ID."""
        filepath = self.storage_dir / f"{checkpoint.checkpoint_id}.json"
        filepath.write_text(checkpoint.to_json())
        self._chain.append(checkpoint.checkpoint_id)

        # Also save the chain index
        chain_file = self.storage_dir / "_chain.json"
        chain_file.write_text(json.dumps(self._chain, indent=2))

        return checkpoint.checkpoint_id

    def load(self, checkpoint_id: str) -> Checkpoint:
        """Load a specific checkpoint by ID."""
        filepath = self.storage_dir / f"{checkpoint_id}.json"
        if not filepath.exists():
            raise FileNotFoundError(f"Checkpoint {checkpoint_id} not found at {filepath}")
        return Checkpoint.from_json(filepath.read_text())

    def load_latest(self) -> Optional[Checkpoint]:
        """Load the most recent checkpoint in the chain."""
        chain_file = self.storage_dir / "_chain.json"
        if chain_file.exists():
            self._chain = json.loads(chain_file.read_text())

        if not self._chain:
            return None

        return self.load(self._chain[-1])

    def get_full_history(self) -> list[Checkpoint]:
        """Load all checkpoints in order. Useful for debugging/analytics."""
        chain_file = self.storage_dir / "_chain.json"
        if chain_file.exists():
            self._chain = json.loads(chain_file.read_text())

        return [self.load(cid) for cid in self._chain]

    def clear(self):
        """Wipe all checkpoints. Use for fresh starts."""
        import shutil
        if self.storage_dir.exists():
            shutil.rmtree(self.storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._chain = []

"""
AetherCheckpoint — Infinite Execution Loop with Context Checkpointing
=====================================================================

Drop-in episodic execution engine for any LLM agent.
Converts stateless tool-calling loops into persistent, long-running processes
with bounded context and unlimited total execution.

Architecture (Cory's Checkpoint Pattern):
    Steps 1..N:   Active execution (tool calls)
    Step N+1:     Checkpoint — distill & persist working memory
    Step N+2:     Rehydrate — reset context, load compressed state
    Repeat forever.

Memory Layers:
    Layer 1 — Working Memory   (ephemeral, current loop only)
    Layer 2 — Episodic Memory  (checkpoint summaries, persistent)
    Layer 3 — Semantic Memory   (long-term knowledge, embeddings)

Created by Cory / AetherPro Technologies LLC
"""

from .engine import CheckpointEngine, CheckpointConfig
from .memory import WorkingMemory, EpisodicMemory, MemoryLayer
from .checkpointer import Checkpointer, CheckpointState
from .loop import InfiniteExecutionLoop

__version__ = "1.0.0"
__all__ = [
    "CheckpointEngine",
    "CheckpointConfig",
    "WorkingMemory",
    "EpisodicMemory",
    "MemoryLayer",
    "Checkpointer",
    "CheckpointState",
    "InfiniteExecutionLoop",
]

"""
Three-Layer Memory Architecture
================================
Layer 1: Working Memory  → Current loop only. Ephemeral. (Redis / in-memory)
Layer 2: Episodic Memory → Checkpoint summaries. Persistent. (Postgres / file)
Layer 3: Semantic Memory → Long-term facts, embeddings. (Weaviate / file)

This maps directly to Cory's existing stack:
  Redis    → Working Memory
  Postgres → Episodic Checkpoints
  Weaviate → Semantic Memory

The file-based implementations below let you develop locally.
Swap in the production backends when you're ready to deploy.
"""

import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# =============================================================================
# LAYER 1: WORKING MEMORY
# =============================================================================

@dataclass
class ToolResult:
    """A single tool call and its result within the current episode."""
    step_number: int
    tool_name: str
    tool_input: dict[str, Any]
    tool_output: Any
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tokens_used: int = 0  # Estimated token count for this result
    success: bool = True
    error: Optional[str] = None


class WorkingMemory(ABC):
    """Layer 1: Ephemeral memory for the current execution episode.

    Think of this as RAM - fast, limited, cleared every episode.
    """

    @abstractmethod
    def append(self, result: ToolResult) -> None:
        """Add a tool result to working memory."""

    @abstractmethod
    def get_all(self) -> list[ToolResult]:
        """Get all results in the current episode."""

    @abstractmethod
    def get_token_count(self) -> int:
        """Estimate total tokens currently in working memory."""

    @abstractmethod
    def clear(self) -> None:
        """Wipe working memory for a fresh episode."""

    @abstractmethod
    def to_summary_text(self) -> str:
        """Render working memory as text for the distillation step."""


class InMemoryWorkingMemory(WorkingMemory):
    """File/in-memory implementation for development."""

    def __init__(self):
        self._results: list[ToolResult] = []

    def append(self, result: ToolResult) -> None:
        self._results.append(result)

    def get_all(self) -> list[ToolResult]:
        return list(self._results)

    def get_token_count(self) -> int:
        return sum(r.tokens_used for r in self._results)

    def clear(self) -> None:
        self._results = []

    def to_summary_text(self) -> str:
        lines = []
        for r in self._results:
            status = "✓" if r.success else "✗"
            lines.append(f"Step {r.step_number} [{status}] {r.tool_name}: {_truncate(str(r.tool_output), 200)}")
            if r.error:
                lines.append(f"  Error: {r.error}")
        return "\n".join(lines)


class RedisWorkingMemory(WorkingMemory):
    """Production Redis implementation.

    Stores working memory in a Redis list keyed by session ID.
    Auto-expires after the episode timeout.
    """

    def __init__(self, redis_url: str, session_id: str, ttl: int = 600):
        try:
            import redis
        except ImportError:
            raise ImportError("pip install redis  -- required for RedisWorkingMemory")

        self._client = redis.from_url(redis_url, decode_responses=True)
        self._key = f"aether:working_memory:{session_id}"
        self._ttl = ttl

    def append(self, result: ToolResult) -> None:
        data = json.dumps({
            "step_number": result.step_number,
            "tool_name": result.tool_name,
            "tool_input": result.tool_input,
            "tool_output": result.tool_output,
            "timestamp": result.timestamp,
            "tokens_used": result.tokens_used,
            "success": result.success,
            "error": result.error,
        }, default=str)
        self._client.rpush(self._key, data)
        self._client.expire(self._key, self._ttl)

    def get_all(self) -> list[ToolResult]:
        raw_list = self._client.lrange(self._key, 0, -1)
        results = []
        for raw in raw_list:
            d = json.loads(raw)
            results.append(ToolResult(**d))
        return results

    def get_token_count(self) -> int:
        return sum(r.tokens_used for r in self.get_all())

    def clear(self) -> None:
        self._client.delete(self._key)

    def to_summary_text(self) -> str:
        lines = []
        for r in self.get_all():
            status = "✓" if r.success else "✗"
            lines.append(f"Step {r.step_number} [{status}] {r.tool_name}: {_truncate(str(r.tool_output), 200)}")
            if r.error:
                lines.append(f"  Error: {r.error}")
        return "\n".join(lines)


# =============================================================================
# LAYER 2: EPISODIC MEMORY
# =============================================================================

class EpisodicMemory(ABC):
    """Layer 2: Persistent checkpoint storage.

    Think of this as disk - slower, unlimited, survives restarts.
    """

    @abstractmethod
    def save_checkpoint(self, checkpoint_data: dict) -> str:
        """Save a checkpoint. Returns checkpoint ID."""

    @abstractmethod
    def load_checkpoint(self, checkpoint_id: str) -> Optional[dict]:
        """Load a checkpoint by ID."""

    @abstractmethod
    def load_latest(self) -> Optional[dict]:
        """Load the most recent checkpoint."""

    @abstractmethod
    def list_checkpoints(self) -> list[dict]:
        """List all checkpoints with metadata."""


class FileEpisodicMemory(EpisodicMemory):
    """File-based implementation for development."""

    def __init__(self, storage_dir: str = "./checkpoints"):
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(self, checkpoint_data: dict) -> str:
        cid = checkpoint_data.get("checkpoint_id", f"chkpt_{int(time.time())}")
        filepath = self._dir / f"{cid}.json"
        filepath.write_text(json.dumps(checkpoint_data, indent=2, default=str))

        # Update chain index
        chain = self._load_chain()
        chain.append(cid)
        (self._dir / "_chain.json").write_text(json.dumps(chain))
        return cid

    def load_checkpoint(self, checkpoint_id: str) -> Optional[dict]:
        filepath = self._dir / f"{checkpoint_id}.json"
        if filepath.exists():
            return json.loads(filepath.read_text())
        return None

    def load_latest(self) -> Optional[dict]:
        chain = self._load_chain()
        if not chain:
            return None
        return self.load_checkpoint(chain[-1])

    def list_checkpoints(self) -> list[dict]:
        chain = self._load_chain()
        results = []
        for cid in chain:
            cp = self.load_checkpoint(cid)
            if cp:
                results.append({
                    "checkpoint_id": cp.get("checkpoint_id"),
                    "created_at": cp.get("created_at"),
                    "episode_number": cp.get("episode_number"),
                    "objective": cp.get("objective", "")[:100],
                })
        return results

    def _load_chain(self) -> list[str]:
        chain_file = self._dir / "_chain.json"
        if chain_file.exists():
            return json.loads(chain_file.read_text())
        return []


class PostgresEpisodicMemory(EpisodicMemory):
    """Production Postgres implementation.

    Schema auto-creates on first use.
    """

    CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS aether_checkpoints (
        checkpoint_id TEXT PRIMARY KEY,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        episode_number INTEGER,
        objective TEXT,
        data JSONB NOT NULL,
        parent_checkpoint_id TEXT REFERENCES aether_checkpoints(checkpoint_id)
    );
    CREATE INDEX IF NOT EXISTS idx_checkpoints_created ON aether_checkpoints(created_at DESC);
    """

    def __init__(self, postgres_url: str):
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError:
            raise ImportError("pip install psycopg2-binary  -- required for PostgresEpisodicMemory")

        self._conn = psycopg2.connect(postgres_url)
        self._conn.autocommit = True
        with self._conn.cursor() as cur:
            cur.execute(self.CREATE_TABLE)

    def save_checkpoint(self, checkpoint_data: dict) -> str:
        import psycopg2.extras
        cid = checkpoint_data.get("checkpoint_id")
        with self._conn.cursor() as cur:
            cur.execute(
                """INSERT INTO aether_checkpoints (checkpoint_id, episode_number, objective, data, parent_checkpoint_id)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (checkpoint_id) DO UPDATE SET data = EXCLUDED.data""",
                (
                    cid,
                    checkpoint_data.get("episode_number"),
                    checkpoint_data.get("objective"),
                    json.dumps(checkpoint_data, default=str),
                    checkpoint_data.get("parent_checkpoint_id"),
                )
            )
        return cid

    def load_checkpoint(self, checkpoint_id: str) -> Optional[dict]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT data FROM aether_checkpoints WHERE checkpoint_id = %s", (checkpoint_id,))
            row = cur.fetchone()
            if row:
                return json.loads(row[0]) if isinstance(row[0], str) else row[0]
        return None

    def load_latest(self) -> Optional[dict]:
        with self._conn.cursor() as cur:
            cur.execute("SELECT data FROM aether_checkpoints ORDER BY created_at DESC LIMIT 1")
            row = cur.fetchone()
            if row:
                return json.loads(row[0]) if isinstance(row[0], str) else row[0]
        return None

    def list_checkpoints(self) -> list[dict]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT checkpoint_id, created_at, episode_number, objective FROM aether_checkpoints ORDER BY created_at"
            )
            return [
                {"checkpoint_id": r[0], "created_at": str(r[1]), "episode_number": r[2], "objective": r[3]}
                for r in cur.fetchall()
            ]


# =============================================================================
# LAYER 3: SEMANTIC MEMORY
# =============================================================================

class SemanticMemory(ABC):
    """Layer 3: Long-term knowledge with semantic search.

    Facts, learned patterns, and embeddings that persist across all tasks.
    """

    @abstractmethod
    def store(self, key: str, content: str, metadata: dict[str, Any] = None) -> None:
        """Store a fact or piece of knowledge."""

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Semantic search over stored knowledge."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove a piece of knowledge."""


class FileSemanticMemory(SemanticMemory):
    """File-based implementation for development.
    Uses simple keyword matching. Swap for Weaviate in production.
    """

    def __init__(self, storage_dir: str = "./semantic_memory"):
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self._dir / "_index.json"
        self._index: dict[str, dict] = {}
        if self._index_file.exists():
            self._index = json.loads(self._index_file.read_text())

    def store(self, key: str, content: str, metadata: dict[str, Any] = None) -> None:
        self._index[key] = {
            "content": content,
            "metadata": metadata or {},
            "stored_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save_index()

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        query_words = set(query.lower().split())
        scored = []
        for key, entry in self._index.items():
            content_words = set(entry["content"].lower().split())
            overlap = len(query_words & content_words)
            if overlap > 0:
                scored.append((overlap, key, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"key": key, "content": entry["content"], "metadata": entry["metadata"], "score": score}
            for score, key, entry in scored[:top_k]
        ]

    def delete(self, key: str) -> None:
        self._index.pop(key, None)
        self._save_index()

    def _save_index(self):
        self._index_file.write_text(json.dumps(self._index, indent=2, default=str))


class WeaviateSemanticMemory(SemanticMemory):
    """Production Weaviate implementation with real vector search."""

    COLLECTION_NAME = "AetherSemanticMemory"

    def __init__(self, weaviate_url: str):
        try:
            import weaviate
        except ImportError:
            raise ImportError("pip install weaviate-client  -- required for WeaviateSemanticMemory")

        self._client = weaviate.Client(url=weaviate_url)
        self._ensure_schema()

    def _ensure_schema(self):
        if not self._client.schema.contains({"class": self.COLLECTION_NAME}):
            self._client.schema.create_class({
                "class": self.COLLECTION_NAME,
                "vectorizer": "text2vec-transformers",
                "properties": [
                    {"name": "key", "dataType": ["text"]},
                    {"name": "content", "dataType": ["text"]},
                    {"name": "metadata", "dataType": ["text"]},
                    {"name": "stored_at", "dataType": ["date"]},
                ],
            })

    def store(self, key: str, content: str, metadata: dict[str, Any] = None) -> None:
        self._client.data_object.create(
            class_name=self.COLLECTION_NAME,
            data_object={
                "key": key,
                "content": content,
                "metadata": json.dumps(metadata or {}),
                "stored_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        result = (
            self._client.query
            .get(self.COLLECTION_NAME, ["key", "content", "metadata"])
            .with_near_text({"concepts": [query]})
            .with_limit(top_k)
            .do()
        )
        items = result.get("data", {}).get("Get", {}).get(self.COLLECTION_NAME, [])
        return [
            {
                "key": item["key"],
                "content": item["content"],
                "metadata": json.loads(item.get("metadata", "{}")),
            }
            for item in items
        ]

    def delete(self, key: str) -> None:
        self._client.batch.delete_objects(
            class_name=self.COLLECTION_NAME,
            where={"path": ["key"], "operator": "Equal", "valueText": key},
        )


# =============================================================================
# HELPERS
# =============================================================================

def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."

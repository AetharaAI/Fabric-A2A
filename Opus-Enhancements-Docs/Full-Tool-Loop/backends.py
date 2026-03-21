"""
Production Backend Adapters
============================

Drop-in backends for your existing AetherPro stack:
    - Redis  → Working memory (fast ephemeral state)
    - Postgres → Episodic memory (checkpoint persistence)
    - Weaviate → Semantic memory (long-term knowledge/embeddings)

Install dependencies as needed:
    pip install redis asyncpg weaviate-client
"""

from __future__ import annotations

import json
import time
import hashlib
from typing import Optional

from .memory import EpisodicMemoryBackend, EpisodeCheckpoint


# ─────────────────────────────────────────────────────────
# PostgreSQL Backend — Episodic Memory (Checkpoints)
# ─────────────────────────────────────────────────────────

class PostgresEpisodicBackend(EpisodicMemoryBackend):
    """
    PostgreSQL backend for persistent checkpoint storage.
    
    Uses asyncpg for async operations. Maps to your existing
    Postgres infrastructure.
    
    Setup:
        backend = PostgresEpisodicBackend(dsn="postgresql://user:pass@host/db")
        await backend.initialize()  # Creates table if not exists
        
        engine = CheckpointEngine(episodic_backend=backend)
    """

    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS agent_checkpoints (
        checkpoint_id TEXT PRIMARY KEY,
        objective_hash TEXT NOT NULL,
        episode_number INTEGER NOT NULL,
        objective TEXT NOT NULL,
        progress_summary TEXT,
        current_state JSONB DEFAULT '{}'::jsonb,
        next_actions JSONB DEFAULT '[]'::jsonb,
        key_results JSONB DEFAULT '[]'::jsonb,
        dependencies JSONB DEFAULT '[]'::jsonb,
        metadata JSONB DEFAULT '{}'::jsonb,
        token_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW(),
        
        -- Index for fast lookups by objective
        CONSTRAINT idx_objective_episode UNIQUE (objective_hash, episode_number)
    );
    
    CREATE INDEX IF NOT EXISTS idx_checkpoints_objective 
        ON agent_checkpoints(objective_hash);
    CREATE INDEX IF NOT EXISTS idx_checkpoints_created 
        ON agent_checkpoints(created_at DESC);
    """

    def __init__(self, dsn: str = None, pool=None):
        """
        Args:
            dsn: PostgreSQL connection string
            pool: Existing asyncpg pool (if you already have one)
        """
        self._dsn = dsn
        self._pool = pool

    async def initialize(self):
        """Create table and indexes. Call once on startup."""
        if not self._pool:
            import asyncpg
            self._pool = await asyncpg.create_pool(self._dsn, min_size=2, max_size=10)
        
        async with self._pool.acquire() as conn:
            await conn.execute(self.CREATE_TABLE_SQL)

    def _hash_objective(self, objective: str) -> str:
        return hashlib.sha256(objective.encode()).hexdigest()[:12]

    async def save_checkpoint(self, checkpoint: EpisodeCheckpoint) -> str:
        obj_hash = self._hash_objective(checkpoint.objective)
        
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_checkpoints 
                    (checkpoint_id, objective_hash, episode_number, objective,
                     progress_summary, current_state, next_actions, key_results,
                     dependencies, metadata, token_count)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (checkpoint_id) DO UPDATE SET
                    current_state = EXCLUDED.current_state,
                    next_actions = EXCLUDED.next_actions,
                    key_results = EXCLUDED.key_results
                """,
                checkpoint.checkpoint_id,
                obj_hash,
                checkpoint.episode_number,
                checkpoint.objective,
                checkpoint.progress_summary,
                json.dumps(checkpoint.current_state),
                json.dumps(checkpoint.next_actions),
                json.dumps(checkpoint.key_results),
                json.dumps(checkpoint.dependencies),
                json.dumps(checkpoint.metadata),
                checkpoint.token_count,
            )
        return checkpoint.checkpoint_id

    async def load_checkpoint(self, checkpoint_id: str) -> Optional[EpisodeCheckpoint]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM agent_checkpoints WHERE checkpoint_id = $1",
                checkpoint_id,
            )
        if not row:
            return None
        return self._row_to_checkpoint(row)

    async def load_latest(self, objective_hash: str) -> Optional[EpisodeCheckpoint]:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM agent_checkpoints 
                WHERE objective_hash = $1 
                ORDER BY episode_number DESC LIMIT 1
                """,
                objective_hash,
            )
        if not row:
            return None
        return self._row_to_checkpoint(row)

    async def list_checkpoints(
        self, objective_hash: str, limit: int = 20
    ) -> list[EpisodeCheckpoint]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM agent_checkpoints 
                WHERE objective_hash = $1 
                ORDER BY episode_number DESC LIMIT $2
                """,
                objective_hash, limit,
            )
        return [self._row_to_checkpoint(r) for r in rows]

    def _row_to_checkpoint(self, row) -> EpisodeCheckpoint:
        return EpisodeCheckpoint(
            checkpoint_id=row["checkpoint_id"],
            episode_number=row["episode_number"],
            objective=row["objective"],
            progress_summary=row["progress_summary"],
            current_state=json.loads(row["current_state"]),
            next_actions=json.loads(row["next_actions"]),
            key_results=json.loads(row["key_results"]),
            dependencies=json.loads(row["dependencies"]),
            metadata=json.loads(row["metadata"]),
            token_count=row["token_count"],
            timestamp=row["created_at"].timestamp() if row["created_at"] else time.time(),
        )


# ─────────────────────────────────────────────────────────
# Redis Backend — Fast Working Memory + Episodic Cache
# ─────────────────────────────────────────────────────────

class RedisEpisodicBackend(EpisodicMemoryBackend):
    """
    Redis backend for fast checkpoint storage.
    
    Good for:
        - Development / testing
        - Short-lived tasks where you don't need permanent history
        - Caching layer in front of Postgres
        
    Uses sorted sets for ordering and hash maps for data.
    
    Setup:
        import redis.asyncio as redis
        client = redis.Redis(host="localhost", port=6379)
        backend = RedisEpisodicBackend(client, ttl=86400)  # 24hr TTL
    """

    def __init__(self, redis_client, prefix: str = "aether:chkpt", ttl: int = 86400):
        self._redis = redis_client
        self._prefix = prefix
        self._ttl = ttl

    def _key(self, *parts) -> str:
        return ":".join([self._prefix] + list(parts))

    async def save_checkpoint(self, checkpoint: EpisodeCheckpoint) -> str:
        obj_hash = hashlib.sha256(checkpoint.objective.encode()).hexdigest()[:12]
        
        # Store checkpoint data as hash
        data_key = self._key("data", checkpoint.checkpoint_id)
        await self._redis.hset(data_key, mapping={
            "json": json.dumps(checkpoint.to_dict()),
        })
        if self._ttl:
            await self._redis.expire(data_key, self._ttl)

        # Add to sorted set for ordering
        index_key = self._key("idx", obj_hash)
        await self._redis.zadd(
            index_key,
            {checkpoint.checkpoint_id: checkpoint.episode_number},
        )
        if self._ttl:
            await self._redis.expire(index_key, self._ttl)

        return checkpoint.checkpoint_id

    async def load_checkpoint(self, checkpoint_id: str) -> Optional[EpisodeCheckpoint]:
        data_key = self._key("data", checkpoint_id)
        raw = await self._redis.hget(data_key, "json")
        if not raw:
            return None
        data = json.loads(raw)
        return EpisodeCheckpoint(**data)

    async def load_latest(self, objective_hash: str) -> Optional[EpisodeCheckpoint]:
        index_key = self._key("idx", objective_hash)
        # Get highest scored (latest episode) member
        members = await self._redis.zrevrange(index_key, 0, 0)
        if not members:
            return None
        checkpoint_id = members[0] if isinstance(members[0], str) else members[0].decode()
        return await self.load_checkpoint(checkpoint_id)

    async def list_checkpoints(
        self, objective_hash: str, limit: int = 20
    ) -> list[EpisodeCheckpoint]:
        index_key = self._key("idx", objective_hash)
        members = await self._redis.zrevrange(index_key, 0, limit - 1)
        results = []
        for m in members:
            cid = m if isinstance(m, str) else m.decode()
            chk = await self.load_checkpoint(cid)
            if chk:
                results.append(chk)
        return results


# ─────────────────────────────────────────────────────────
# Weaviate Integration — Semantic Memory (Layer 3)
# ─────────────────────────────────────────────────────────

class WeaviateSemanticMemory:
    """
    Weaviate-backed semantic memory for long-term knowledge.
    
    This is Layer 3 — the deep storage for facts, embeddings,
    and knowledge graph data that persists across ALL objectives.
    
    Use cases:
        - Store learned facts from completed tasks
        - Retrieve relevant past knowledge for new tasks
        - Build up institutional knowledge over time
    
    Setup:
        import weaviate
        client = weaviate.Client("http://localhost:8080")
        semantic = WeaviateSemanticMemory(client)
        await semantic.initialize()
    """

    COLLECTION_NAME = "AetherAgentMemory"

    def __init__(self, weaviate_client, collection_name: str = None):
        self._client = weaviate_client
        self._collection = collection_name or self.COLLECTION_NAME

    async def initialize(self):
        """Create the Weaviate collection if it doesn't exist."""
        # Check if collection exists
        try:
            schema = self._client.schema.get()
            existing = [c["class"] for c in schema.get("classes", [])]
            if self._collection in existing:
                return
        except Exception:
            pass

        # Create collection with properties for agent memory
        self._client.schema.create_class({
            "class": self._collection,
            "description": "Long-term semantic memory for AetherPro agents",
            "vectorizer": "text2vec-transformers",  # or your preferred vectorizer
            "properties": [
                {
                    "name": "content",
                    "dataType": ["text"],
                    "description": "The knowledge content",
                },
                {
                    "name": "category",
                    "dataType": ["text"],
                    "description": "Knowledge category (fact, skill, preference, etc.)",
                },
                {
                    "name": "source_objective",
                    "dataType": ["text"],
                    "description": "Which objective generated this knowledge",
                },
                {
                    "name": "confidence",
                    "dataType": ["number"],
                    "description": "Confidence score 0-1",
                },
                {
                    "name": "agent_id",
                    "dataType": ["text"],
                    "description": "Which agent created this memory",
                },
                {
                    "name": "created_at",
                    "dataType": ["date"],
                },
            ],
        })

    def store_knowledge(
        self,
        content: str,
        category: str = "fact",
        source_objective: str = "",
        confidence: float = 0.8,
        agent_id: str = "default",
    ) -> str:
        """Store a piece of long-term knowledge."""
        from datetime import datetime
        
        result = self._client.data_object.create(
            class_name=self._collection,
            data_object={
                "content": content,
                "category": category,
                "source_objective": source_objective,
                "confidence": confidence,
                "agent_id": agent_id,
                "created_at": datetime.utcnow().isoformat(),
            },
        )
        return result

    def recall(
        self,
        query: str,
        limit: int = 5,
        category: str = None,
        min_confidence: float = 0.5,
    ) -> list[dict]:
        """
        Semantic search for relevant knowledge.
        
        This is how your agent recalls past learnings that are
        relevant to the current task.
        """
        search = (
            self._client.query
            .get(self._collection, ["content", "category", "confidence", "source_objective"])
            .with_near_text({"concepts": [query]})
            .with_limit(limit)
        )

        if category:
            search = search.with_where({
                "path": ["category"],
                "operator": "Equal",
                "valueText": category,
            })

        result = search.do()
        items = result.get("data", {}).get("Get", {}).get(self._collection, [])
        
        # Filter by confidence
        return [
            item for item in items
            if item.get("confidence", 0) >= min_confidence
        ]

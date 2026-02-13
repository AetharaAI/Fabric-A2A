# AetherCheckpoint: Infinite Execution Engine

**Checkpointed Episodic Execution with Context Compaction and Loop Rehydration**

Converts any stateless LLM agent into a persistent process with theoretically unlimited runtime.

---

## The Core Idea

LLM agents die because they treat context like infinite storage. It's not. Context is RAM — fast, expensive, limited.

This engine implements a simple cycle:

```
┌─────────────────────────────────────────────────────────┐
│                    EPISODE N                             │
│                                                         │
│  Step 1:  Execute tool call                             │
│  Step 2:  Execute tool call                             │
│  ...                                                    │
│  Step 10: Execute tool call                             │
│  Step 11: CHECKPOINT — distill working memory → state   │
│  Step 12: REHYDRATE — clear context, load checkpoint    │
│                                                         │
│                    ↓ repeat ↓                            │
│                                                         │
│                    EPISODE N+1                           │
│  (starts fresh with only the distilled checkpoint)      │
└─────────────────────────────────────────────────────────┘
```

Context stays bounded. Total execution is unbounded. The agent becomes architecturally immortal.

---

## Three-Layer Memory Architecture

```
┌──────────────────────────────────────────────────────┐
│  Layer 1: WORKING MEMORY  (Redis / In-Memory)        │
│  Current episode only. Ephemeral. Fast.              │
│  Analogy: CPU Cache / RAM                            │
├──────────────────────────────────────────────────────┤
│  Layer 2: EPISODIC MEMORY  (Postgres / File)         │
│  Checkpoint summaries. Persistent continuation state.│
│  Analogy: Disk / SSD                                 │
├──────────────────────────────────────────────────────┤
│  Layer 3: SEMANTIC MEMORY  (Weaviate / File)         │
│  Long-term facts, embeddings, knowledge graph.       │
│  Analogy: Archive / Library                          │
└──────────────────────────────────────────────────────┘
```

Maps directly to the AetherPro stack:
- **Redis** → Working Memory
- **PostgreSQL** → Episodic Checkpoints
- **Weaviate** → Semantic Memory

---

## Quick Start

### 1. Install

```bash
cd checkpoint-engine
pip install -e .
```

### 2. Implement Your Agent (3 methods)

```python
class MyAgent:
    def decide_action(self, system_prompt, messages) -> dict:
        """Ask the LLM what to do next. Return {"tool": "...", "input": {...}}"""
        ...

    def execute_tool(self, tool_name, tool_input) -> Any:
        """Execute the tool call. Return the result."""
        ...

    def distill_checkpoint(self, objective, working_memory_text, previous_checkpoint) -> dict:
        """Compress working memory into structured state."""
        ...
```

### 3. Run

```python
from aether_checkpoint import CheckpointEngine, MemoryConfig

config = MemoryConfig.for_model("apriel-1.5-15b-thinker")  # Auto-tunes to model
engine = CheckpointEngine(agent=MyAgent(), config=config)
result = engine.run("Deploy the AetherOS Docker stack")
```

### 4. Resume (crash recovery)

```python
engine.resume()  # Picks up from latest checkpoint
engine.resume(checkpoint_id="chkpt_abc123")  # Specific checkpoint
```

---

## Configuration

### Auto-Configure by Model

```python
config = MemoryConfig.for_model("apriel-1.5-15b-thinker")  # 32K context
config = MemoryConfig.for_model("kimi-k2")                  # 128K context
config = MemoryConfig.for_model("minimax-m2")               # 64K context
```

The factory calculates optimal episode length based on context window size.

### Manual Configuration

```python
config = MemoryConfig(
    max_steps_per_episode=10,    # Active work steps
    checkpoint_step=11,          # Save state
    reset_step=12,               # Rehydrate

    # Adaptive triggers (override fixed step count)
    active_triggers=[
        CheckpointTrigger.FIXED_STEP,
        CheckpointTrigger.TOKEN_THRESHOLD,
        CheckpointTrigger.SUBTASK_COMPLETE,
        CheckpointTrigger.ERROR_RECOVERY,
    ],
    token_threshold=12_000,      # Checkpoint when tokens exceed this

    # Safety limits
    max_total_episodes=100,
    max_total_tool_calls=1000,
)
```

### Production Backends

```python
from aether_checkpoint.config import StorageBackend

config.working_memory_backend = StorageBackend.REDIS
config.episodic_memory_backend = StorageBackend.POSTGRES
config.semantic_memory_backend = StorageBackend.WEAVIATE
config.redis_url = "redis://localhost:6379/0"
config.postgres_url = "postgresql://localhost:5432/aether_checkpoints"
config.weaviate_url = "http://localhost:8080"
```

---

## What Makes a Good Checkpoint (The Most Important Part)

The checkpoint distillation step (Step 11) is the brain of the system.

### ❌ Bad Checkpoint (Archaeology)

```
"Here are the last 10 tool outputs..."
(wastes tokens on raw data the next episode doesn't need)
```

### ✅ Good Checkpoint (Navigation)

```json
{
    "objective": "Deploy Docker stack",
    "progress": ["Base image built", "Redis running", "Postgres running"],
    "state": {
        "containers_running": ["redis", "postgres"],
        "blocking_issue": "nginx.conf syntax error line 42"
    },
    "next_action": "Fix nginx.conf, then start nginx container",
    "dependencies": ["valid nginx.conf"],
    "errors": ["nginx syntax error on line 42"]
}
```

Compact. Actionable. Everything the next episode needs. Nothing it doesn't.

---

## File Structure

```
aether_checkpoint/
├── __init__.py          # Public API
├── config.py            # All configuration and tunables
├── checkpoint.py        # Checkpoint data model + manager
├── memory.py            # Three-layer memory (Working, Episodic, Semantic)
├── loop.py              # The execution loop (the core engine)
├── engine.py            # Top-level orchestrator
└── prompts.py           # Distillation prompt templates

example_usage.py         # Simple demo (simulated agent)
integration_template.py  # Real LLM agent template (copy and customize)
```

---

## Key Design Decisions

1. **Framework-agnostic**: Works with any agent (LangChain, CrewAI, custom, AetherAgent). Just implement 3 methods.

2. **Backend-swappable**: File-based for dev, Redis/Postgres/Weaviate for production. Same code, different config.

3. **Adaptive checkpointing**: Fixed step counts work (your original 12), but the engine also supports token-threshold, subtask-completion, and error-recovery triggers.

4. **Safety limits**: Hard caps on episodes and tool calls prevent runaway execution.

5. **Resume from anywhere**: Every checkpoint is a valid restart point. Crash recovery is built in.

6. **Observable**: Event callbacks let you monitor every step, checkpoint, and rehydration in real time.

---

## The Fundamental Insight

> Context is not memory. Context is working state.
> Memory lives outside the model.

This engine implements that insight. The model gets a fresh, bounded context every episode. All accumulated intelligence lives in the checkpoint chain — outside the model, persistent, and unlimited.

The agent stops being `function(input) → output` and becomes `process(state) → new_state`.

That's the difference between a chatbot and an operating system.

---

*AetherPro Technologies LLC — Sovereign AI Infrastructure*

# AetherCheckpoint — Infinite Execution Loop with Context Checkpointing

**Convert any stateless LLM agent into a persistent, long-running process with bounded context and unlimited execution.**

Built by AetherPro Technologies LLC.

---

## The Problem

LLM agents die because they treat context like infinite RAM. It's not. Context is CPU cache — fast, expensive, and limited. When it fills up, the agent crashes.

## The Solution

Checkpointed episodic execution with context compaction and loop rehydration:

```
┌─────────────────────────────────────────────────────────────┐
│                    INFINITE EXECUTION LOOP                   │
│                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                │
│  │ Step 1   │──▶│ Step 2   │──▶│  ...N    │  Active Work   │
│  │ Tool Call│   │ Tool Call │   │ Tool Call│                 │
│  └──────────┘   └──────────┘   └──────────┘                │
│       │                              │                       │
│       ▼                              ▼                       │
│  ┌─────────────────────────────────────────┐                │
│  │         WORKING MEMORY (ephemeral)       │                │
│  │    ~8,000 tokens of current episode      │                │
│  └─────────────────┬───────────────────────┘                │
│                     │                                        │
│              ┌──────▼──────┐                                │
│              │ CHECKPOINT  │  Step N+1: Distill & Persist   │
│              │  (Step N+1) │  Compress 8K tokens → 200      │
│              └──────┬──────┘                                │
│                     │                                        │
│              ┌──────▼──────┐                                │
│              │  REHYDRATE  │  Step N+2: Reset & Reload      │
│              │  (Step N+2) │  Fresh context, full continuity │
│              └──────┬──────┘                                │
│                     │                                        │
│                     └──────── LOOP FOREVER ──────────────────┘
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Three-Tier Memory Architecture

| Layer | Purpose | Lifetime | Backend |
|-------|---------|----------|---------|
| **Working Memory** | Current episode tool results | Ephemeral (cleared each checkpoint) | In-memory / Redis |
| **Episodic Memory** | Compressed checkpoint summaries | Persistent across episodes | PostgreSQL / Redis |
| **Semantic Memory** | Long-term knowledge & embeddings | Permanent | Weaviate |

Maps to your existing stack: **Redis → Working**, **Postgres → Episodic**, **Weaviate → Semantic**

---

## Quick Start

### Install

```bash
# Core (no external dependencies)
pip install -e .

# With production backends
pip install -e ".[all]"     # Redis + Postgres + Weaviate
pip install -e ".[postgres]" # Just Postgres
```

### Minimal Integration (10 lines added to existing agent)

```python
from aether_checkpoint import CheckpointEngine

# Create engine
engine = CheckpointEngine.create_simple(
    objective="Deploy Docker pipeline for AetherOS",
    steps_per_episode=10,
    token_budget=8000,
)

# Your existing agent loop
while not done:
    context = engine.get_context()          # ← Rehydrated state
    action = model.decide(context)
    result = execute_tool(action)
    engine.record_tool_call(name, input, result)  # ← Record

    if engine.should_checkpoint():           # ← Check
        await engine.run_checkpoint()        # ← Distill + Reset
```

That's it. Your agent can now run forever with bounded context.

### Full Execution Loop (for new agents)

```python
from aether_checkpoint import InfiniteExecutionLoop
from aether_checkpoint.loop import AgentAction

async def my_decider(context: str) -> AgentAction:
    # Your model decides what to do based on context
    return AgentAction(tool_name="search", tool_input={"q": "test"})

async def my_executor(name: str, input: dict):
    # Your tool execution logic
    return {"result": "done"}

loop = InfiniteExecutionLoop(
    objective="Build complete deployment pipeline",
    model_decider=my_decider,
    tool_executor=my_executor,
    steps_per_episode=10,
)

result = await loop.run()  # Runs until complete
```

### Production Setup (Postgres + LLM Distillation)

```python
from aether_checkpoint import CheckpointEngine, CheckpointConfig
from aether_checkpoint.backends import PostgresEpisodicBackend
from aether_checkpoint.checkpointer import LLMDistillation

# Postgres for persistent checkpoints
pg = PostgresEpisodicBackend(dsn="postgresql://user:pass@host/db")
await pg.initialize()

# LLM-powered distillation (use your Apriel Thinker model)
async def distill_llm(prompt: str) -> str:
    return await your_vllm_client.complete(prompt)

engine = CheckpointEngine(
    config=CheckpointConfig(
        objective="Deploy AetherOS fleet",
        max_steps_per_episode=10,
        max_tokens_per_episode=12000,
        adaptive_checkpointing=True,
    ),
    episodic_backend=pg,
    distillation_strategy=LLMDistillation(llm_callable=distill_llm),
)
```

---

## What Makes a Good Checkpoint (Critical)

**Bad checkpoint** (raw logs — archaeology):
```
Here are the last 10 tool outputs: [10,000 tokens of raw JSON]
```

**Good checkpoint** (distilled state — navigation):
```
OBJECTIVE: Build Docker deployment pipeline

PROGRESS (after 3 episodes):
  ✓ Docker base image created
  ✓ Redis container configured
  ✓ PostgreSQL container configured

CURRENT STATE:
  deployment: incomplete
  blocking_issue: none

NEXT ACTIONS:
  → Configure nginx reverse proxy
  → Add TLS certificates

CHECKPOINT: chkpt_a1b2c3d4 | Episode 3
```

200 tokens instead of 10,000. That's the magic.

---

## Adaptive vs Fixed Checkpointing

**Fixed** (your original "12" idea): Checkpoint every N steps. Simple, predictable.

**Adaptive** (evolved version): Checkpoint when any trigger fires:
- Token budget at 75%+
- Step count reaches max
- Subtask completes
- Error detected
- Custom trigger

```python
# Add custom triggers
engine.add_checkpoint_trigger(
    lambda e: any("error" in str(r.tool_output).lower()
                  for r in e.working_memory.entries[-1:])
)
```

---

## Architecture

```
aether_checkpoint/
├── __init__.py          # Package entry point
├── memory.py            # WorkingMemory + EpisodicMemory + backends
├── checkpointer.py      # State distillation (rule-based + LLM)
├── engine.py            # CheckpointEngine (main orchestrator)
├── loop.py              # InfiniteExecutionLoop (high-level wrapper)
└── backends.py          # Production backends (Postgres, Redis, Weaviate)
```

---

## The Computer Science Behind This

This pattern maps to how operating systems achieve infinite runtime:

| Agent Concept | OS Equivalent | Your Stack |
|---------------|---------------|------------|
| Current tool call | CPU registers | In-memory |
| Working memory | RAM | Redis |
| Episodic checkpoints | Disk | PostgreSQL |
| Semantic memory | Deep storage | Weaviate |
| Checkpoint cycle | Context switch | Engine |
| Rehydration | Process restore | Engine |

The agent becomes a **persistent process**, not a **stateless function**.

```
function(input) → output        ← chatbot
process(state) → new_state      ← operating system
```

---

## License

MIT — AetherPro Technologies LLC

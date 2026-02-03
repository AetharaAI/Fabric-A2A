# Fabric A2A Message Bus Implementation Plan

## Executive Summary

You already have **Redis Stack running locally** (port 16381 with RedisInsight). This document outlines how to add **asynchronous agent-to-agent messaging** to Fabric using Redis Streams, while maintaining your **sovereign infrastructure** on OVH.

---

## What You're Building

### Current State (Sync Only)
```
Agent A ──HTTP POST──> Fabric ──HTTP POST──> Agent B
     <──Wait 30s──────       <──Wait 30s──────
```

### Future State (Sync + Async)
```
SYNC (existing):
Agent A ──HTTP POST──> Fabric ──HTTP POST──> Agent B

ASYNC (new):
Agent A ──XADD──> Redis Stream ──XREADGROUP──> Agent B
     <──Immediate ACK──                    (Processes when ready)
     
Agent A publishes ──PUBLISH──> Topic ──SUBSCRIBE──> Agent C, D, E
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FABRIC MCP SERVER                             │
│                                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   HTTP API  │  │   Redis     │  │    Agent Workers        │  │
│  │   (MCP)     │  │   Gateway   │  │    (Async Consumers)    │  │
│  │             │  │             │  │                         │  │
│  │ • tools     │  │ • Streams   │  │ • percy_worker          │  │
│  │ • agents    │  │ • Pub/Sub   │  │ • coder_worker          │  │
│  │ • messages  │  │ • ACLs      │  │ • memory_worker         │  │
│  └─────────────┘  └──────┬──────┘  └─────────────────────────┘  │
│                          │                                       │
│           ┌──────────────┼────────────────┐                     │
│           ▼              ▼                ▼                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ agent:{id}:  │ │  analytics.* │ │   shared:*   │            │
│  │   inbox      │ │  system.*    │ │   (topics)   │            │
│  │              │ │  agent.*     │ │              │            │
│  │ • Persistent │ │              │ │              │            │
│  │ • Ordered    │ │              │ │              │            │
│  │ • Consumer   │ │              │ │              │            │
│  │   Groups     │ │              │ │              │            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
         ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Local Dev  │    │   OVH R64    │    │   OVH R64    │
│  Redis Stack │    │   Valkey     │    │  Redis Stack │
│  (Current)   │    │  (Future)    │    │  (Now)       │
│  Port 16381  │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
```

---

## Files Created

| File | Purpose |
|------|---------|
| `fabric_message_bus.py` | Core message bus with Redis Streams + Pub/Sub |
| `docker-compose.redis.yml` | Redis Stack deployment for R64 |
| `config/redis/users.acl.example` | Agent security isolation |

---

## New MCP Tools

### 1. `fabric.message.send`
```json
{
  "name": "fabric.message.send",
  "arguments": {
    "to_agent": "percy",
    "from_agent": "coder",
    "message_type": "task",
    "payload": {
      "task_type": "code_review",
      "pr_id": "123"
    },
    "priority": "high",
    "reply_to": "agent:coder:results"
  }
}

// Response:
{
  "message_id": "msg:uuid",
  "status": "queued",
  "stream_id": "1234567890-0"
}
```

### 2. `fabric.message.receive`
```json
{
  "name": "fabric.message.receive",
  "arguments": {
    "agent_id": "percy",
    "count": 5,
    "block_ms": 30000,
    "consumer_group": "percy_workers"
  }
}

// Response:
{
  "messages": [
    {
      "id": "msg:uuid",
      "from_agent": "coder",
      "message_type": "task",
      "payload": {...},
      "_stream_id": "1234567890-0"
    }
  ]
}
```

### 3. `fabric.message.acknowledge`
```json
{
  "name": "fabric.message.acknowledge",
  "arguments": {
    "agent_id": "percy",
    "message_ids": ["1234567890-0"],
    "consumer_group": "percy_workers"
  }
}
```

### 4. `fabric.message.publish`
```json
{
  "name": "fabric.message.publish",
  "arguments": {
    "topic": "analytics.insights",
    "message": {
      "pattern": "unusual_traffic",
      "data": {...}
    },
    "from_agent": "monitoring"
  }
}
```

### 5. `fabric.message.queue_status`
```json
{
  "name": "fabric.message.queue_status",
  "arguments": {
    "agent_id": "percy"
  }
}

// Response:
{
  "agent_id": "percy",
  "queue_depth": 42,
  "stream_info": {...}
}
```

---

## Deployment Options

### Option 1: Redis Stack on R64 (Recommended Now)

**On your R64 node:**
```bash
# Create directories
sudo mkdir -p /opt/redis/data
sudo mkdir -p /opt/redis/config

# Copy ACL file
sudo cp config/redis/users.acl.example /opt/redis/users.acl
sudo chmod 600 /opt/redis/users.acl

# Edit with real passwords
sudo nano /opt/redis/users.acl

# Deploy
docker-compose -f docker-compose.redis.yml up -d
```

**Access via SSH tunnel:**
```bash
# From your laptop
ssh -L 6379:localhost:6379 root@your-r64-ip
ssh -L 8001:localhost:8001 root@your-r64-ip

# Now localhost:6379 = R64 Redis
# Now localhost:8001 = RedisInsight UI
```

### Option 2: Keep Local Redis Stack (Dev Mode)

You already have this running. Just use:
```python
bus = FabricMessageBus(redis_url="redis://localhost:6379")
```

---

## Security Model (ACLs)

Each agent gets isolated credentials:

```
percy_agent ────────> Can only access agent:percy:* keys
coder_agent ────────> Can only access agent:coder:* keys
memory_agent ───────> Can only access agent:memory:* keys
        │                    │
        └────────────────────┘
              Can all publish to shared:* topics
```

**Benefits:**
- Percy cannot read Coder's private queue
- Compromised agent = limited blast radius
- Audit trail via separate monitoring user

---

## Integration With Your Stack

### With Passport IAM
```python
# Validate agent JWT, then issue Redis ACL token
agent_id = passport.validate_token(jwt)
redis_token = generate_redis_acl_token(agent_id)
# Agent connects with scoped credentials
```

### With Triad Memory
```python
# Auto-store messages in Triad
await triad.store_message(
    message,
    tags=["a2a", message.from_agent, message.to_agent],
    layer="short_term"  # or "long_term" for important decisions
)
```

### With ATP (Analytics)
```python
# Every message = telemetry event
atp.record_event("a2a.message", {
    "from": message.from_agent,
    "to": message.to_agent,
    "latency_ms": delivery_time,
    "payload_size": len(json.dumps(message.payload))
})
```

---

## Migration Path

### Phase 1: Deploy Redis (This Week)
1. Deploy Redis Stack to R64
2. Test SSH tunnel access
3. Verify ACLs work

### Phase 2: Add Message Bus (Next Week)
1. Integrate `fabric_message_bus.py` into server.py
2. Add MCP endpoints
3. Test agent-to-agent messaging

### Phase 3: Agent Workers (Following Week)
1. Create background worker processes
2. Migrate from sync calls to async streams
3. Add consumer groups for scaling

---

## Why This Fits Your Sovereign Vision

✅ **100% Open Source**: Redis Stack = BSD license  
✅ **Self-Hosted**: Your R64 node, your data  
✅ **No External APIs**: No AWS SQS, no Google Pub/Sub  
✅ **Air-Gappable**: Can run completely offline  
✅ **Predictable Costs**: Fixed OVH pricing  

---

## Next Steps

1. **Deploy Redis Stack to R64** using `docker-compose.redis.yml`
2. **Test locally first** using your existing Redis Stack
3. **Integrate message bus** into `server.py`
4. **Create worker example** showing Percy consuming tasks

Want me to:
- **A**: Create the server.py integration code?
- **B**: Create a worker example (Percy consuming tasks)?
- **C**: Create deployment scripts for R64?
- **D**: Something else?

---

**Bottom Line:** You're already 90% there. You have Redis Stack running, you have the vision, and now you have the code. This gives Fabric true async A2A capabilities while keeping everything sovereign on your OVH infrastructure. 🔥

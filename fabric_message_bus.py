"""
Fabric Message Bus - Async A2A Communication via Redis Streams

This module provides async agent-to-agent messaging on top of the 
synchronous MCP tool calling. Uses Redis Streams for persistence
and Pub/Sub for real-time notifications.

Architecture:
- Streams: Persistent task queues (agent:{id}:tasks)
- Pub/Sub: Real-time broadcasts (topics like analytics.insights)
- Consumer Groups: Load balancing across agent replicas

Author: AetherPro Technologies
"""

import os
import json
import uuid
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable, AsyncIterator
from dataclasses import dataclass, asdict
from enum import Enum

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class MessageStatus(Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class FabricMessage:
    """Standard message format for A2A communication"""
    id: str
    from_agent: str
    to_agent: str
    message_type: str  # e.g., "task", "response", "event", "heartbeat"
    payload: Dict[str, Any]
    timestamp: str
    priority: int = 2  # MessagePriority.NORMAL
    ttl_seconds: int = 86400  # 24 hours default
    reply_to: Optional[str] = None  # Queue/topic for response
    correlation_id: Optional[str] = None  # For tracking conversation threads
    
    @classmethod
    def create(
        cls,
        from_agent: str,
        to_agent: str,
        message_type: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        reply_to: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> "FabricMessage":
        return cls(
            id=f"msg:{uuid.uuid4()}",
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            payload=payload,
            timestamp=datetime.utcnow().isoformat(),
            priority=priority.value,
            reply_to=reply_to,
            correlation_id=correlation_id or str(uuid.uuid4())
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FabricMessage":
        return cls(**data)


class FabricMessageBus:
    """
    Async message bus for agent-to-agent communication.
    
    Provides:
    - Direct messaging (private queues)
    - Pub/Sub broadcasting (topics)
    - Consumer groups for load balancing
    - Message persistence and replay
    """
    
    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        redis_url: Optional[str] = None
    ):
        """
        Initialize message bus.
        
        Args:
            redis_client: Existing Redis client (sovereign mode)
            redis_url: Redis connection URL (e.g., redis://localhost:6379)
        """
        if redis_client:
            self.r = redis_client
        elif redis_url:
            self.r = redis.from_url(redis_url, decode_responses=True)
        else:
            # Default to env var or localhost
            url = os.getenv("REDIS_URL", "redis://localhost:6379")
            self.r = redis.from_url(url, decode_responses=True)
        
        self._pubsub = None
        self._subscribed = False
    
    async def ping(self) -> bool:
        """Check Redis connectivity"""
        try:
            return await self.r.ping()
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False
    
    # =======================================================================
    # Direct Messaging (Streams)
    # =======================================================================
    
    async def send_message(
        self,
        message: FabricMessage,
        wait_for_delivery: bool = False,
        timeout_ms: int = 5000
    ) -> Dict[str, Any]:
        """
        Send a message to an agent's queue.
        
        Args:
            message: The message to send
            wait_for_delivery: If True, block until message is consumed
            timeout_ms: How long to wait for delivery (if wait_for_delivery)
            
        Returns:
            {"message_id": "...", "status": "queued", "stream_id": "..."}
        """
        stream_key = f"agent:{message.to_agent}:inbox"
        
        # Add message to stream
        stream_id = await self.r.xadd(
            stream_key,
            {"data": json.dumps(message.to_dict())},
            maxlen=10000  # Keep last 10k messages per agent
        )
        
        # Publish real-time notification
        await self.r.publish(
            f"agent.{message.to_agent}.new_message",
            json.dumps({
                "from": message.from_agent,
                "type": message.message_type,
                "priority": message.priority,
                "message_id": message.id
            })
        )
        
        result = {
            "message_id": message.id,
            "status": "queued",
            "stream_id": stream_id,
            "timestamp": message.timestamp
        }
        
        if wait_for_delivery:
            # TODO: Implement delivery confirmation via separate mechanism
            pass
        
        logger.debug(f"Message {message.id} sent to {message.to_agent}")
        return result
    
    async def send_task(
        self,
        from_agent: str,
        to_agent: str,
        task_type: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        reply_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """Convenience method for task delegation"""
        message = FabricMessage.create(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type="task",
            payload={"task_type": task_type, **payload},
            priority=priority,
            reply_to=reply_to or f"agent:{from_agent}:results"
        )
        return await self.send_message(message)
    
    async def receive_messages(
        self,
        agent_id: str,
        count: int = 10,
        block_ms: int = 5000,
        consumer_group: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Receive messages for an agent.
        
        Args:
            agent_id: The agent's ID
            count: Max messages to receive
            block_ms: How long to wait (0 = forever)
            consumer_group: If set, use consumer group for load balancing
            
        Returns:
            List of messages with their stream IDs
        """
        stream_key = f"agent:{agent_id}:inbox"
        messages = []
        
        if consumer_group:
            # Use consumer group (for scaled agents with multiple replicas)
            try:
                # Auto-create group if not exists
                try:
                    await self.r.xgroup_create(stream_key, consumer_group, id="0", mkstream=True)
                except redis.ResponseError:
                    pass  # Group already exists
                
                # Read as consumer
                consumer_name = f"{agent_id}_{os.getpid()}"
                entries = await self.r.xreadgroup(
                    groupname=consumer_group,
                    consumername=consumer_name,
                    streams={stream_key: ">"},  # Only undelivered messages
                    count=count,
                    block=block_ms
                )
                
                for stream, stream_entries in entries:
                    for msg_id, fields in stream_entries:
                        data = json.loads(fields["data"])
                        data["_stream_id"] = msg_id
                        data["_consumer_group"] = consumer_group
                        messages.append(data)
                        
            except Exception as e:
                logger.error(f"Consumer group read failed: {e}")
        else:
            # Simple read (for single-instance agents)
            entries = await self.r.xread(
                streams={stream_key: "0"},  # From beginning
                count=count,
                block=block_ms
            )
            
            for stream, stream_entries in entries:
                for msg_id, fields in stream_entries:
                    data = json.loads(fields["data"])
                    data["_stream_id"] = msg_id
                    messages.append(data)
        
        return messages
    
    async def acknowledge_message(
        self,
        agent_id: str,
        stream_id: str,
        consumer_group: Optional[str] = None
    ) -> bool:
        """
        Acknowledge message processing (removes from pending).
        Call this after successfully processing a message.
        """
        stream_key = f"agent:{agent_id}:inbox"
        
        if consumer_group:
            await self.r.xack(stream_key, consumer_group, stream_id)
        else:
            # For non-consumer-group, delete the message
            await self.r.xdel(stream_key, stream_id)
        
        return True
    
    async def get_pending_messages(
        self,
        agent_id: str,
        consumer_group: str
    ) -> List[Dict[str, Any]]:
        """Get messages that were delivered but not acknowledged"""
        stream_key = f"agent:{agent_id}:inbox"
        
        pending = await self.r.xpending_range(
            stream_key,
            consumer_group,
            min="-",
            max="+",
            count=100
        )
        
        return [
            {
                "stream_id": item["message_id"],
                "consumer": item["consumer"],
                "idle_time_ms": item["time_since_delivered"],
                "delivery_count": item["times_delivered"]
            }
            for item in pending
        ]
    
    # =======================================================================
    # Pub/Sub (Broadcast)
    # =======================================================================
    
    async def publish(
        self,
        topic: str,
        message: Dict[str, Any],
        from_agent: Optional[str] = None
    ) -> int:
        """
        Publish message to a topic (broadcast).
        
        Returns:
            Number of subscribers that received the message
        """
        payload = {
            "data": message,
            "from": from_agent,
            "timestamp": datetime.utcnow().isoformat(),
            "topic": topic
        }
        
        recipients = await self.r.publish(topic, json.dumps(payload))
        logger.debug(f"Published to {topic}: {recipients} recipients")
        return recipients
    
    async def subscribe(
        self,
        topics: List[str],
        callback: Callable[[str, Dict[str, Any]], None],
        pattern: bool = False
    ) -> "FabricMessageBus":
        """
        Subscribe to topics for real-time updates.
        
        Args:
            topics: List of topic names (or patterns if pattern=True)
            callback: Function(channel, message) to call on message
            pattern: If True, topics are patterns like "agent.*.events"
        """
        self._pubsub = self.r.pubsub()
        
        if pattern:
            await self._pubsub.psubscribe(*topics)
        else:
            await self._pubsub.subscribe(*topics)
        
        self._subscribed = True
        
        # Start listener task
        asyncio.create_task(self._listen_loop(callback, pattern))
        
        return self
    
    async def _listen_loop(
        self,
        callback: Callable[[str, Dict[str, Any]], None],
        pattern: bool
    ):
        """Background task to listen for pub/sub messages"""
        async for message in self._pubsub.listen():
            if message["type"] in ("message", "pmessage"):
                channel = message.get("channel") or message.get("pattern")
                data = json.loads(message["data"])
                try:
                    callback(channel, data)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
    
    async def unsubscribe(self):
        """Unsubscribe from all topics"""
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
            self._subscribed = False
    
    # =======================================================================
    # Utility Methods
    # =======================================================================
    
    async def get_queue_depth(self, agent_id: str) -> int:
        """Get number of pending messages for an agent"""
        stream_key = f"agent:{agent_id}:inbox"
        return await self.r.xlen(stream_key)
    
    async def get_stream_info(self, agent_id: str) -> Dict[str, Any]:
        """Get detailed info about an agent's stream"""
        stream_key = f"agent:{agent_id}:inbox"
        info = await self.r.xinfo_stream(stream_key)
        return {
            "length": info["length"],
            "radix_tree_keys": info["radix-tree-keys"],
            "radix_tree_nodes": info["radix-tree-nodes"],
            "groups": info["groups"],
            "last_generated_id": info["last-generated-id"],
            "first_entry": info.get("first-entry"),
            "last_entry": info.get("last-entry")
        }
    
    async def trim_stream(self, agent_id: str, max_len: int = 10000) -> int:
        """Trim agent's stream to max length"""
        stream_key = f"agent:{agent_id}:inbox"
        return await self.r.xtrim(stream_key, maxlen=max_len)
    
    async def close(self):
        """Close Redis connection"""
        if self._subscribed:
            await self.unsubscribe()
        await self.r.close()


# =============================================================================
# MCP Tool Integration
# =============================================================================

class FabricMessageBusMCP:
    """
    MCP tool interface for the message bus.
    
    Exposes:
    - fabric.message.send
    - fabric.message.receive
    - fabric.message.publish
    - fabric.message.subscribe
    """
    
    def __init__(self, message_bus: FabricMessageBus):
        self.bus = message_bus
    
    async def send(
        self,
        to_agent: str,
        from_agent: str,
        message_type: str,
        payload: Dict[str, Any],
        priority: str = "normal",
        reply_to: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """MCP tool: fabric.message.send"""
        priority_map = {
            "low": MessagePriority.LOW,
            "normal": MessagePriority.NORMAL,
            "high": MessagePriority.HIGH,
            "urgent": MessagePriority.URGENT
        }
        
        message = FabricMessage.create(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            payload=payload,
            priority=priority_map.get(priority, MessagePriority.NORMAL),
            reply_to=reply_to
        )
        
        return await self.bus.send_message(message)
    
    async def receive(
        self,
        agent_id: str,
        count: int = 10,
        block_ms: int = 5000,
        consumer_group: Optional[str] = None,
        auto_ack: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """MCP tool: fabric.message.receive"""
        messages = await self.bus.receive_messages(
            agent_id=agent_id,
            count=count,
            block_ms=block_ms,
            consumer_group=consumer_group
        )
        
        if auto_ack:
            for msg in messages:
                stream_id = msg.get("_stream_id")
                if stream_id:
                    await self.bus.acknowledge_message(
                        agent_id, stream_id, consumer_group
                    )
        
        return {
            "messages": messages,
            "count": len(messages),
            "agent_id": agent_id
        }
    
    async def publish(
        self,
        topic: str,
        message: Dict[str, Any],
        from_agent: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """MCP tool: fabric.message.publish"""
        recipients = await self.bus.publish(topic, message, from_agent)
        return {
            "topic": topic,
            "recipients": recipients,
            "published": True
        }
    
    async def acknowledge(
        self,
        agent_id: str,
        message_ids: List[str],
        consumer_group: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """MCP tool: fabric.message.acknowledge"""
        acked = []
        for msg_id in message_ids:
            # Note: message_ids here should be stream_ids
            success = await self.bus.acknowledge_message(
                agent_id, msg_id, consumer_group
            )
            acked.append({"id": msg_id, "acked": success})
        
        return {"acknowledged": acked}
    
    async def queue_status(
        self,
        agent_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """MCP tool: fabric.message.queue_status"""
        depth = await self.bus.get_queue_depth(agent_id)
        try:
            info = await self.bus.get_stream_info(agent_id)
        except:
            info = {}
        
        return {
            "agent_id": agent_id,
            "queue_depth": depth,
            "stream_info": info
        }


# =============================================================================
# Usage Examples
# =============================================================================

"""
# Example 1: Agent A sends task to Agent B
bus = FabricMessageBus(redis_url="redis://localhost:6379")

# Send
result = await bus.send_task(
    from_agent="coder",
    to_agent="percy",
    task_type="code_review",
    payload={"pr_id": "123", "files": ["main.py"]},
    priority=MessagePriority.HIGH
)

# Receive (in Percy agent)
messages = await bus.receive_messages("percy", count=1, block_ms=10000)
for msg in messages:
    print(f"Task from {msg['from_agent']}: {msg['payload']['task_type']}")
    # Process...
    await bus.acknowledge_message("percy", msg["_stream_id"])

# Example 2: Pub/Sub for events
# Subscribe
await bus.subscribe(
    topics=["analytics.insights", "system.alerts"],
    callback=lambda ch, msg: print(f"Event on {ch}: {msg}")
)

# Publish
await bus.publish("analytics.insights", {
    "pattern": "unusual_traffic",
    "severity": "high",
    "data": {...}
}, from_agent="monitoring_agent")

# Example 3: Consumer groups (scaled agents)
# Multiple Coder instances share the load
messages = await bus.receive_messages(
    "coder",
    consumer_group="coder_workers",  # All instances use same group
    count=5
)

# Example 4: MCP Tool Call
mcp = FabricMessageBusMCP(bus)

# Via HTTP POST /mcp/call
{
  "name": "fabric.message.send",
  "arguments": {
    "to_agent": "percy",
    "from_agent": "coder",
    "message_type": "task",
    "payload": {"action": "review_code", "pr_id": "123"},
    "priority": "high"
  }
}

{
  "name": "fabric.message.receive",
  "arguments": {
    "agent_id": "percy",
    "count": 5,
    "block_ms": 30000
  }
}
"""

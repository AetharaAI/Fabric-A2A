"""
Fabric A2A SDK - Messaging Client
Async messaging using Redis Streams and Pub/Sub for agent-to-agent communication.
"""

import json
import asyncio
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum


class MessagePriority(Enum):
    """Message priority levels"""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class Message:
    """Message structure for A2A communication"""

    id: str
    from_agent: str
    to_agent: str
    message_type: str
    payload: Dict[str, Any]
    timestamp: str
    priority: int = 2
    reply_to: Optional[str] = None
    correlation_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        return cls(
            id=data.get("id", ""),
            from_agent=data.get("from_agent", ""),
            to_agent=data.get("to_agent", ""),
            message_type=data.get("message_type", ""),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", ""),
            priority=data.get("priority", 2),
            reply_to=data.get("reply_to"),
            correlation_id=data.get("correlation_id"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "priority": self.priority,
            "reply_to": self.reply_to,
            "correlation_id": self.correlation_id,
        }


class MessagingClient:
    """
    Client for async messaging via Redis Streams and Pub/Sub.

    Requires Redis ACL to be configured for the agent.

    Args:
        agent_id: Your agent's identifier
        redis_url: Redis connection URL (e.g., "redis://localhost:6379")
        password: Redis password for ACL authentication
        consumer_group: Optional consumer group for load balancing

    Example:
        >>> client = MessagingClient(agent_id="mastro", redis_url="redis://localhost:6379")
        >>> await client.send_message("percy", "task", {"task": "Analyze this"})
        >>> messages = await client.receive_messages()
    """

    def __init__(
        self,
        agent_id: str,
        redis_url: str = "redis://localhost:6379",
        password: Optional[str] = None,
        consumer_group: Optional[str] = None,
    ):
        self.agent_id = agent_id
        self.redis_url = redis_url
        self.password = password
        self.consumer_group = consumer_group
        self._redis = None
        self._pubsub = None
        self._running = False
        self._handlers: Dict[str, Callable[[Message], Awaitable]] = {}
        self._listener_task: Optional[asyncio.Task] = None

    async def connect(self):
        """Connect to Redis"""
        import redis.asyncio as redis

        self._redis = redis.from_url(
            self.redis_url, decode_responses=True, password=self.password
        )
        await self._redis.ping()

    async def close(self):
        """Close Redis connection"""
        self._running = False
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()

    async def send_message(
        self,
        to_agent: str,
        message_type: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        reply_to: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a message to another agent via Redis Stream.

        Args:
            to_agent: Target agent ID
            message_type: Type of message (task, response, event, etc.)
            payload: Message content
            priority: Message priority
            reply_to: Optional queue to send response to
            correlation_id: Optional correlation ID for tracking

        Returns:
            Dict with message_id and stream_id
        """
        import uuid
        from datetime import datetime

        if not self._redis:
            await self.connect()

        message = Message(
            id=f"msg:{uuid.uuid4()}",
            from_agent=self.agent_id,
            to_agent=to_agent,
            message_type=message_type,
            payload=payload,
            timestamp=datetime.utcnow().isoformat(),
            priority=priority.value,
            reply_to=reply_to or f"agent:{self.agent_id}:results",
            correlation_id=correlation_id or str(uuid.uuid4()),
        )

        stream_key = f"agent:{to_agent}:inbox"
        stream_id = await self._redis.xadd(
            stream_key, {"data": json.dumps(message.to_dict())}, maxlen=10000
        )

        # Publish notification
        await self._redis.publish(
            f"agent.{to_agent}.new_message",
            json.dumps(
                {"from": self.agent_id, "type": message_type, "message_id": message.id}
            ),
        )

        return {"message_id": message.id, "stream_id": stream_id, "status": "queued"}

    async def send_task(
        self,
        to_agent: str,
        task_type: str,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
    ) -> Dict[str, Any]:
        """Convenience method for sending tasks"""
        return await self.send_message(
            to_agent=to_agent,
            message_type="task",
            payload={"task_type": task_type, **payload},
            priority=priority,
        )

    async def receive_messages(
        self, count: int = 10, block_ms: int = 5000
    ) -> List[Message]:
        """
        Receive messages from your inbox stream.

        Args:
            count: Maximum messages to receive
            block_ms: Block timeout in milliseconds (0 = forever)

        Returns:
            List of Message objects
        """
        if not self._redis:
            await self.connect()

        stream_key = f"agent:{self.agent_id}:inbox"

        if self.consumer_group:
            try:
                await self._redis.xgroup_create(
                    stream_key, self.consumer_group, id="0", mkstream=True
                )
            except Exception:
                pass

            entries = await self._redis.xreadgroup(
                groupname=self.consumer_group,
                consumername=f"{self.agent_id}_{id(self)}",
                streams={stream_key: ">"},
                count=count,
                block=block_ms,
            )
        else:
            entries = await self._redis.xread(
                streams={stream_key: "0"}, count=count, block=block_ms
            )

        messages = []
        for stream, stream_entries in entries:
            for msg_id, fields in stream_entries:
                data = json.loads(fields["data"])
                msg = Message.from_dict(data)
                msg.id = msg_id
                messages.append(msg)

        return messages

    async def acknowledge(self, message_id: str) -> bool:
        """Acknowledge message processing"""
        if not self._redis:
            await self.connect()

        stream_key = f"agent:{self.agent_id}:inbox"
        if self.consumer_group:
            await self._redis.xack(stream_key, self.consumer_group, message_id)
        else:
            await self._redis.xdel(stream_key, message_id)
        return True

    async def get_queue_depth(self) -> int:
        """Get number of pending messages"""
        if not self._redis:
            await self.connect()

        stream_key = f"agent:{self.agent_id}:inbox"
        return await self._redis.xlen(stream_key)

    async def subscribe(
        self,
        topic: str,
        handler: Callable[[Dict[str, Any]], Awaitable[None]],
        pattern: bool = False,
    ):
        """
        Subscribe to a Pub/Sub topic.

        Args:
            topic: Topic name (or pattern if pattern=True)
            handler: Async callback function(topic, message)
            pattern: Use pattern subscription
        """
        if not self._redis:
            await self.connect()

        self._pubsub = self._redis.pubsub()

        if pattern:
            await self._pubsub.psubscribe(topic)
        else:
            await self._pubsub.subscribe(topic)

        self._running = True
        self._listener_task = asyncio.create_task(self._listen_loop(handler, pattern))

    async def _listen_loop(
        self, handler: Callable[[Dict[str, Any]], Awaitable[None]], pattern: bool
    ):
        """Background listener for pub/sub messages"""
        async for message in self._pubsub.listen():
            if message["type"] in ("message", "pmessage"):
                channel = message.get("channel") or message.get("pattern")
                try:
                    data = json.loads(message["data"])
                    await handler(channel, data)
                except Exception as e:
                    print(f"Pubsub handler error: {e}")

    async def publish(self, topic: str, message: Dict[str, Any]) -> int:
        """
        Publish message to a topic.

        Args:
            topic: Topic name
            message: Message to publish

        Returns:
            Number of subscribers that received the message
        """
        if not self._redis:
            await self.connect()

        return await self._redis.publish(topic, json.dumps(message))

    def on(self, message_type: str):
        """
        Decorator to register message handler.

        Example:
            @client.on("task")
            async def handle_task(msg: Message):
                print(f"Got task: {msg.payload}")
        """

        def decorator(func: Callable[[Message], Awaitable]):
            self._handlers[message_type] = func
            return func

        return decorator

    async def start_listening(self, block_ms: int = 5000):
        """
        Start listening for messages and routing to handlers.

        Args:
            block_ms: How long to wait for messages
        """
        self._running = True
        while self._running:
            try:
                messages = await self.receive_messages(count=1, block_ms=block_ms)
                for msg in messages:
                    handler = self._handlers.get(msg.message_type)
                    if handler:
                        try:
                            await handler(msg)
                            await self.acknowledge(msg.id)
                        except Exception as e:
                            print(f"Handler error: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Message loop error: {e}")
                await asyncio.sleep(1)


class AsyncMessagingClient(MessagingClient):
    """
    Async messaging client with streaming support.

    Provides streaming response handling for agent calls.
    """

    async def send_message_streaming(
        self,
        to_agent: str,
        message_type: str,
        payload: Dict[str, Any],
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
        priority: MessagePriority = MessagePriority.NORMAL,
    ):
        """
        Send message and stream response.

        Args:
            to_agent: Target agent ID
            message_type: Type of message
            payload: Message content
            callback: Async callback for each response chunk
            priority: Message priority
        """
        import uuid
        from datetime import datetime

        if not self._redis:
            await self.connect()

        correlation_id = str(uuid.uuid4())
        reply_to = f"agent:{self.agent_id}:responses:{correlation_id}"

        message = Message(
            id=f"msg:{uuid.uuid4()}",
            from_agent=self.agent_id,
            to_agent=to_agent,
            message_type=message_type,
            payload=payload,
            timestamp=datetime.utcnow().isoformat(),
            priority=priority.value,
            reply_to=reply_to,
            correlation_id=correlation_id,
        )

        stream_key = f"agent:{to_agent}:inbox"
        await self._redis.xadd(
            stream_key, {"data": json.dumps(message.to_dict())}, maxlen=10000
        )

        # Subscribe to response channel
        response_channel = f"agent.{self.agent_id}.response.{correlation_id}"
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(response_channel)

        async for response_msg in pubsub.listen():
            if response_msg["type"] == "message":
                data = json.loads(response_msg["data"])
                await callback(data)

        await pubsub.unsubscribe(response_channel)
        await pubsub.close()

    async def get_stream_info(self) -> Dict[str, Any]:
        """Get info about your inbox stream"""
        if not self._redis:
            await self.connect()

        stream_key = f"agent:{self.agent_id}:inbox"
        try:
            info = await self._redis.xinfo_stream(stream_key)
            return {
                "length": info.get("length", 0),
                "groups": info.get("groups", 0),
                "last_id": info.get("last-generated-id", "0"),
            }
        except Exception:
            return {"length": 0, "groups": 0, "last_id": "0"}

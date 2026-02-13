"""
Fabric A2A SDK - Streaming Support
Server-Sent Events (SSE) and WebSocket streaming for agent responses.
"""

import asyncio
import json
from typing import Optional, Dict, Any, Callable, AsyncIterator
from enum import Enum
from dataclasses import dataclass


class StreamEventType(Enum):
    """Types of streaming events"""

    STATUS = "status"
    TOKEN = "token"
    ERROR = "error"
    FINAL = "final"
    STARTED = "started"
    PROGRESS = "progress"
    COMPLETED = "completed"


@dataclass
class StreamEvent:
    """A streaming event from the server"""

    event: str
    data: Dict[str, Any]
    trace_id: Optional[str] = None
    span_id: Optional[str] = None

    @classmethod
    def from_line(cls, line: str) -> Optional["StreamEvent"]:
        """Parse from SSE format line"""
        if not line.startswith("data:"):
            return None
        data_str = line[5:].strip()
        try:
            data = json.loads(data_str)
            return cls(
                event=data.get("event", "message"),
                data=data.get("data", {}),
                trace_id=data.get("trace", {}).get("trace_id"),
                span_id=data.get("trace", {}).get("span_id"),
            )
        except json.JSONDecodeError:
            return None


class StreamIterator:
    """
    Iterator for parsing SSE streams.

    Example:
        async for event in StreamIterator(response):
            print(f"Event: {event.event}, Data: {event.data}")
    """

    def __init__(self, response):
        self.response = response
        self._buffer = ""

    def __aiter__(self):
        return self

    async def __anext__(self) -> StreamEvent:
        """Get next event from stream"""
        while True:
            # Find line boundary
            if "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                event = StreamEvent.from_line(line)
                if event:
                    return event
            else:
                # Read more data
                chunk = await self.response.content.read(1024)
                if not chunk:
                    raise StopAsyncIteration
                self._buffer += chunk.decode("utf-8")


async def stream_sse(
    url: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    on_token: Optional[Callable[[str], None]] = None,
    on_status: Optional[Callable[[Dict], None]] = None,
    on_final: Optional[Callable[[Dict], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """
    Make a streaming request and handle SSE events.

    Args:
        url: Full URL for the request
        headers: HTTP headers including Authorization
        payload: Request payload
        on_token: Callback for token events (partial response)
        on_status: Callback for status events
        on_final: Callback for final event
        on_error: Callback for error events

    Returns:
        Final response dict
    """
    import httpx

    async with httpx.AsyncClient() as client:
        async with client.stream(
            method="POST", url=url, headers=headers, json=payload
        ) as response:
            final_result = None

            async for event in StreamIterator(response):
                if event.event == StreamEventType.TOKEN.value:
                    if on_token:
                        on_token(event.data.get("text", ""))
                elif event.event == StreamEventType.STATUS.value:
                    if on_status:
                        on_status(event.data)
                elif event.event == StreamEventType.FINAL.value:
                    final_result = event.data
                    if on_final:
                        on_final(event.data)
                elif event.event == StreamEventType.ERROR.value:
                    if on_error:
                        on_error(event.data.get("message", "Unknown error"))
                elif event.event == StreamEventType.COMPLETED.value:
                    final_result = event.data

            return final_result or {}


class StreamingResult:
    """
    Handle streaming responses with callbacks.

    Example:
        >>> result = StreamingResult()
        >>> await client.agents.call_streaming(
        ...     "percy", "reason", "Explain quantum",
        ...     on_token=result.on_token
        ... )
        >>> print(result.full_response)
    """

    def __init__(self):
        self.tokens: List[str] = []
        self.full_text: str = ""
        self.status_events: List[Dict] = []
        self.final_result: Optional[Dict] = None
        self.error: Optional[str] = None

    def on_token(self, text: str):
        """Callback for token events"""
        self.tokens.append(text)
        self.full_text += text

    def on_status(self, status: Dict):
        """Callback for status events"""
        self.status_events.append(status)

    def on_final(self, result: Dict):
        """Callback for final event"""
        self.final_result = result

    def on_error(self, error: str):
        """Callback for error events"""
        self.error = error

    @property
    def is_complete(self) -> bool:
        """Check if stream is complete"""
        return self.final_result is not None or self.error is not None


class WebSocketClient:
    """
    WebSocket client for real-time communication.

    Requires Fabric server to have WebSocket support enabled.

    Example:
        >>> ws = WebSocketClient("ws://fabric.example.com/ws")
        >>> await ws.connect()
        >>> await ws.send_message({"type": "call", ...})
        >>> async for msg in ws.messages():
        ...     print(msg)
    """

    def __init__(self, url: str, token: Optional[str] = None):
        self.url = url
        self.token = token
        self._ws = None
        self._reader_task = None
        self._messages: asyncio.Queue = asyncio.Queue()
        self._running = False

    async def connect(self):
        """Connect to WebSocket endpoint"""
        import httpx

        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with httpx.AsyncClient() as client:
            self._ws = await client.connect(self.url, headers=headers, timeout=30.0)
            self._running = True
            self._reader_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self):
        """Background task to read messages"""
        try:
            async for message in self._ws:
                try:
                    data = json.loads(message)
                    await self._messages.put(data)
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass

    async def send_message(self, data: Dict[str, Any]):
        """Send a message"""
        if self._ws:
            await self._ws.send(json.dumps(data))

    async def send_call(
        self, agent_id: str, capability: str, task: str, context: Optional[Dict] = None
    ):
        """Send an agent call"""
        await self.send_message(
            {
                "type": "call",
                "agent_id": agent_id,
                "capability": capability,
                "task": task,
                "context": context or {},
            }
        )

    async def messages(self) -> AsyncIterator[Dict[str, Any]]:
        """Async iterator for incoming messages"""
        while self._running:
            try:
                msg = await asyncio.wait_for(self._messages.get(), timeout=1.0)
                yield msg
            except asyncio.TimeoutError:
                continue

    async def close(self):
        """Close the connection"""
        self._running = False
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()

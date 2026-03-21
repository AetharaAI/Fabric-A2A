"""
Fabric A2A SDK - Main Client
Synchronous and asynchronous clients for Fabric MCP Server.
"""

import json
from typing import Optional, Dict, Any, List, TYPE_CHECKING

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from fabric_a2a.models import CallResult, HealthStatus
from fabric_a2a.exceptions import (
    FabricError, AuthenticationError, ConnectionError,
    TimeoutError, RateLimitError
)

if TYPE_CHECKING:
    from fabric_a2a.tools import ToolClient
    from fabric_a2a.agents import AgentClient


class FabricClient:
    """Synchronous client for Fabric MCP Server."""

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 60.0,
        max_retries: int = 3
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "fabric-a2a-sdk/0.1.0"
        })

        self._tools: Optional["ToolClient"] = None
        self._agents: Optional["AgentClient"] = None

    @property
    def tools(self) -> "ToolClient":
        if self._tools is None:
            from fabric_a2a.tools import ToolClient
            self._tools = ToolClient(self)
        return self._tools

    @property
    def agents(self) -> "AgentClient":
        if self._agents is None:
            from fabric_a2a.agents import AgentClient
            self._agents = AgentClient(self)
        return self._agents

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        from urllib.parse import urljoin
        url = urljoin(self.base_url, endpoint)
        timeout = timeout or self.timeout

        try:
            response = self.session.request(
                method=method, url=url, json=data, timeout=timeout
            )

            if response.status_code == 429:
                raise RateLimitError(retry_after=int(response.headers.get("Retry-After", 60)))
            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired token")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            raise TimeoutError(operation=f"{method} {endpoint}", timeout=timeout)
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(url=str(e), message=str(e))
        except requests.exceptions.HTTPError as e:
            try:
                error_data = e.response.json()
                raise FabricError(
                    message=error_data.get("error", str(e)),
                    code=error_data.get("error_code", "HTTP_ERROR"),
                    trace_id=error_data.get("trace", {}).get("trace_id"),
                    details=error_data.get("details")
                )
            except (json.JSONDecodeError, AttributeError):
                raise FabricError(message=str(e), code="HTTP_ERROR")

    def call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> CallResult:
        payload = {"name": tool_name, "arguments": arguments}
        response = self._make_request("POST", "/mcp/call", data=payload, timeout=timeout)
        return CallResult(**response)

    def health(self) -> HealthStatus:
        return HealthStatus(**self._make_request("GET", "/health"))

    def list_agents(
        self,
        capability: Optional[str] = None,
        tag: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        args = {}
        if capability:
            args["capability"] = capability
        if tag:
            args["tag"] = tag
        if status:
            args["status"] = status
        return self._make_request("GET", "/mcp/list_agents", data=args).get("agents", [])

    def list_tools(
        self,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        args = {"category": category} if category else {}
        return self._make_request("GET", "/mcp/list_tools", data=args).get("tools", [])

    def close(self):
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class AsyncFabricClient:
    """Asynchronous client for Fabric MCP Server."""

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 60.0,
        max_retries: int = 3
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = None

    async def _get_client(self):
        if self._client is None:
            import httpx
            transport = httpx.AsyncHTTPTransport(retries=self.max_retries)
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                transport=transport,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "fabric-a2a-sdk/0.1.0"
                },
                timeout=httpx.Timeout(self.timeout)
            )
        return self._client

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        import httpx
        client = await self._get_client()

        try:
            response = await client.request(method=method, url=endpoint, json=data)

            if response.status_code == 429:
                raise RateLimitError(retry_after=int(response.headers.get("retry-after", 60)))
            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired token")

            response.raise_for_status()
            return response.json()

        except httpx.TimeoutException:
            raise TimeoutError(operation=f"{method} {endpoint}", timeout=self.timeout)
        except httpx.ConnectError as e:
            raise ConnectionError(url=self.base_url, message=str(e))

    async def call(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> CallResult:
        payload = {"name": tool_name, "arguments": arguments}
        response = await self._make_request("POST", "/mcp/call", data=payload)
        return CallResult(**response)

    async def health(self) -> HealthStatus:
        return HealthStatus(**await self._make_request("GET", "/health"))

    async def list_agents(
        self,
        capability: Optional[str] = None,
        tag: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        args = {}
        if capability:
            args["capability"] = capability
        if tag:
            args["tag"] = tag
        return (await self._make_request("GET", "/mcp/list_agents", data=args)).get("agents", [])

    async def list_tools(
        self,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        args = {"category": category} if category else {}
        return (await self._make_request("GET", "/mcp/list_tools", data=args)).get("tools", [])

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

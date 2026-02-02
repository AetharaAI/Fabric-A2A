"""
Fabric A2A SDK - Main Client
Synchronous and asynchronous clients for Fabric MCP Server.
"""

import json
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from fabric_a2a.models import CallResult, TraceContext, HealthStatus, ServerStatus
from fabric_a2a.exceptions import (
    FabricError, AuthenticationError, ConnectionError,
    AgentNotFoundError, CapabilityNotFoundError, ToolNotFoundError,
    TimeoutError, RateLimitError
)
from fabric_a2a.tools import ToolClient
from fabric_a2a.agents import AgentClient


class FabricClient:
    """
    Synchronous client for Fabric MCP Server.
    
    Args:
        base_url: Fabric server URL (e.g., "https://fabric.perceptor.us")
        token: Authentication token (Bearer token)
        timeout: Default request timeout in seconds
        max_retries: Maximum number of retries for failed requests
    
    Example:
        >>> client = FabricClient("https://fabric.perceptor.us", token="secret")
        >>> result = client.tools.math.calculate("2 + 2")
        >>> print(result)  # 4.0
    """
    
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
        
        # Setup session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Setup default headers
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"fabric-a2a-sdk/0.1.0"
        })
        
        # Sub-clients
        self.tools = ToolClient(self)
        self.agents = AgentClient(self)
    
    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Fabric server"""
        url = urljoin(self.base_url, endpoint)
        timeout = timeout or self.timeout
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                timeout=timeout
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitError(retry_after=retry_after)
            
            # Handle auth errors
            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired token")
            
            # Raise for other HTTP errors
            response.raise_for_status()
            
            # Parse response
            return response.json()
            
        except requests.exceptions.Timeout:
            raise TimeoutError(
                operation=f"{method} {endpoint}",
                timeout=timeout
            )
        except requests.exceptions.ConnectionError as e:
            raise ConnectionError(url=str(e), message=str(e))
        except requests.exceptions.HTTPError as e:
            # Try to parse error response
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
        """
        Make a raw MCP call to the Fabric server.
        
        Args:
            tool_name: Name of the tool/agent to call
            arguments: Arguments to pass
            timeout: Optional timeout override
        
        Returns:
            CallResult with trace information
        
        Raises:
            FabricError: If the call fails
        """
        payload = {
            "name": tool_name,
            "arguments": arguments
        }
        
        response = self._make_request(
            "POST",
            "/mcp/call",
            data=payload,
            timeout=timeout
        )
        
        return CallResult(**response)
    
    def health(self) -> HealthStatus:
        """
        Check server health status.
        
        Returns:
            HealthStatus object
        """
        response = self._make_request("GET", "/health")
        return HealthStatus(**response)
    
    def status(self) -> ServerStatus:
        """
        Get complete server status including available agents and tools.
        
        Returns:
            ServerStatus with all available services
        """
        response = self._make_request("GET", "/monitoring/status")
        
        # Convert timestamp string to datetime
        from datetime import datetime
        if "timestamp" in response and isinstance(response["timestamp"], str):
            response["timestamp"] = datetime.fromisoformat(response["timestamp"].replace("Z", "+00:00"))
        
        return ServerStatus(**response)
    
    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """
        Get trace information by ID.
        
        Args:
            trace_id: The trace ID to look up
        
        Returns:
            Trace information or None if not found
        """
        # This would need a trace endpoint on the server
        # For now, return None
        return None
    
    def close(self):
        """Close the HTTP session"""
        self.session.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


class AsyncFabricClient:
    """
    Asynchronous client for Fabric MCP Server.
    
    Use this for high-concurrency applications.
    
    Example:
        >>> async with AsyncFabricClient("https://fabric.perceptor.us", token="secret") as client:
        >>>     result = await client.tools.math.calculate("2 + 2")
        >>>     print(result)  # 4.0
    """
    
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
        """Lazy initialization of async HTTP client"""
        if self._client is None:
            import httpx
            
            # Setup transport with retries
            transport = httpx.AsyncHTTPTransport(
                retries=self.max_retries
            )
            
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                transport=transport,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": f"fabric-a2a-sdk/0.1.0"
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
        """Make async HTTP request"""
        import httpx
        
        client = await self._get_client()
        
        try:
            response = await client.request(
                method=method,
                url=endpoint,
                json=data
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("retry-after", 60))
                raise RateLimitError(retry_after=retry_after)
            
            # Handle auth errors
            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired token")
            
            # Raise for other errors
            response.raise_for_status()
            
            return response.json()
            
        except httpx.TimeoutException:
            raise TimeoutError(
                operation=f"{method} {endpoint}",
                timeout=self.timeout
            )
        except httpx.ConnectError as e:
            raise ConnectionError(url=self.base_url, message=str(e))
    
    async def call(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> CallResult:
        """Make async MCP call"""
        payload = {
            "name": tool_name,
            "arguments": arguments
        }
        
        response = await self._make_request("POST", "/mcp/call", data=payload)
        return CallResult(**response)
    
    async def health(self) -> HealthStatus:
        """Check server health asynchronously"""
        response = await self._make_request("GET", "/health")
        return HealthStatus(**response)
    
    async def status(self) -> ServerStatus:
        """Get server status asynchronously"""
        response = await self._make_request("GET", "/monitoring/status")
        return ServerStatus(**response)
    
    async def close(self):
        """Close async client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
"""
Built-in Web Tools - HTTP and URL Operations

Refactored to use the new BaseTool plugin architecture.
"""

import os
import re
import aiohttp
import asyncio
from typing import Dict, Any, Optional
from html.parser import HTMLParser
from urllib.parse import urlparse, parse_qs

from tools.base import BaseTool, ToolResult, ToolError


class WebTools(BaseTool):
    """Web request and URL processing tools"""
    
    TOOL_ID = "web"
    CAPABILITIES = {}
    
    @staticmethod
    async def request(url: str, method: str = 'GET', headers: Optional[Dict] = None, 
                      body: Optional[str] = None, timeout: int = 30000, **kwargs) -> ToolResult:
        """Make HTTP request"""
        try:
            async with aiohttp.ClientSession() as session:
                request_kwargs = {
                    'headers': headers or {},
                    'timeout': aiohttp.ClientTimeout(total=timeout / 1000)
                }
                if body and method.upper() in ['POST', 'PUT', 'PATCH']:
                    request_kwargs['data'] = body
                
                start_time = asyncio.get_event_loop().time()
                async with session.request(method.upper(), url, **request_kwargs) as response:
                    elapsed_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
                    response_body = await response.text()
                    
                    return ToolResult({
                        "status_code": response.status,
                        "headers": dict(response.headers),
                        "body": response_body[:100000],
                        "elapsed_ms": elapsed_ms,
                        "url": str(response.url)
                    })
                    
        except asyncio.TimeoutError:
            raise ToolError("TIMEOUT", f"Request timed out after {timeout}ms")
        except Exception as e:
            raise ToolError("REQUEST_ERROR", str(e))
    
    @staticmethod
    async def fetch(url: str, extract_text: bool = True, max_length: int = 50000, **kwargs) -> ToolResult:
        """Fetch and extract content from web page"""
        
        class TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text_parts = []
                self.in_skip_tag = 0
                self.skip_tags = {'script', 'style', 'nav', 'footer', 'header'}
                
            def handle_starttag(self, tag, attrs):
                if tag in self.skip_tags:
                    self.in_skip_tag += 1
                    
            def handle_endtag(self, tag):
                if tag in self.skip_tags:
                    self.in_skip_tag -= 1
                    
            def handle_data(self, data):
                if self.in_skip_tag == 0:
                    self.text_parts.append(data)
                    
            def get_text(self):
                text = ' '.join(self.text_parts)
                text = re.sub(r'\s+', ' ', text).strip()
                return text[:max_length]
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    html = await response.text()
                    
                    title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
                    title = title_match.group(1).strip() if title_match else None
                    
                    links = re.findall(r'href=["\'](https?://[^"\']+)["\']', html)
                    
                    result = {
                        "title": title,
                        "url": str(response.url),
                        "links": list(set(links))[:50],
                        "metadata": {
                            "content_type": response.headers.get('Content-Type'),
                            "length": len(html)
                        }
                    }
                    
                    if extract_text:
                        extractor = TextExtractor()
                        try:
                            extractor.feed(html)
                            result["text"] = extractor.get_text()
                        except:
                            result["text"] = None
                    
                    return ToolResult(result)
                    
        except Exception as e:
            raise ToolError("FETCH_ERROR", str(e))
    
    @staticmethod
    async def parse_url(url: str, **kwargs) -> ToolResult:
        """Parse URL into components"""
        try:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            query = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}
            
            return ToolResult({
                "scheme": parsed.scheme,
                "netloc": parsed.netloc,
                "path": parsed.path,
                "params": parsed.params,
                "query": query,
                "fragment": parsed.fragment,
                "hostname": parsed.hostname,
                "port": parsed.port
            })
            
        except Exception as e:
            raise ToolError("PARSE_ERROR", str(e))
    
    @staticmethod
    async def brave_search(query: str, recency_days: int = 7, max_results: int = 5, **kwargs) -> ToolResult:
        """Live web search using Brave API"""
        key = os.getenv("BRAVE_API_KEY")
        if not key:
            raise ToolError("CONFIG_ERROR", "BRAVE_API_KEY not set")

        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": key
        }
        
        # Build params - only include valid values (no None)
        params = {
            "q": query,
            "count": max_results,
        }
        
        # Add optional parameters only if they have valid values
        if recency_days is not None:
            params["freshness"] = f"pd{recency_days}"

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(url, headers=headers, params=params) as r:
                    r.raise_for_status()
                    data = await r.json()

            results = []
            for item in data.get("web", {}).get("results", [])[:max_results]:
                results.append({
                    "title": item.get("title") or "",
                    "url": item.get("url") or "",
                    "snippet": item.get("description") or "",
                    "age_days": item.get("age") or 0,
                })

            return ToolResult({
                "provider": "brave",
                "query": query,
                "results": results,
            })
            
        except aiohttp.ClientError as e:
            raise ToolError("API_ERROR", f"Brave API request failed: {e}")
        except Exception as e:
            raise ToolError("SEARCH_ERROR", str(e))


# Individual tool classes for registry
class HttpRequestTool(BaseTool):
    TOOL_ID = "web.http_request"
    CAPABILITIES = {"request": "request"}
    
    async def request(self, **kwargs) -> ToolResult:
        return await WebTools.request(**kwargs)


class FetchPageTool(BaseTool):
    TOOL_ID = "web.fetch_page"
    CAPABILITIES = {"fetch": "fetch"}
    
    async def fetch(self, **kwargs) -> ToolResult:
        return await WebTools.fetch(**kwargs)


class ParseURLTool(BaseTool):
    TOOL_ID = "web.parse_url"
    CAPABILITIES = {"parse": "parse_url"}
    
    async def parse_url(self, **kwargs) -> ToolResult:
        return await WebTools.parse_url(**kwargs)


class BraveSearchTool(BaseTool):
    TOOL_ID = "web.brave_search"
    CAPABILITIES = {"search": "brave_search"}
    
    async def brave_search(self, **kwargs) -> ToolResult:
        return await WebTools.brave_search(**kwargs)


# Auto-register
BaseTool.register(HttpRequestTool)
BaseTool.register(FetchPageTool)
BaseTool.register(ParseURLTool)
BaseTool.register(BraveSearchTool)

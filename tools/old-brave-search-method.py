import os
from tools.builtin_tools import ToolResult
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timezone
import requests
import hashlib
import base64
import re
import json

# ============================================================================
# Web Tools - HTTP Requests and Web Searches
# ============================================================================
class WebTools:
    """Web-related tools"""
    @staticmethod
    async def brave_search(query: str, recency_days: int = 7, max_results: int = 5):
        key = os.getenv("BRAVE_API_KEY")
        if not key:
            raise RuntimeError("BRAVE_API_KEY not set")

        url = "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": key
        }
        params = {
            "q": query,
            "recency": recency_days,
            "domains": None
        }

        r = requests.get(url, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        # Normalize to something agents can actually use
        results = []
        for item in data.get("web", {}).get("results", [])[:max_results]:
            results.append({
                "title": item.get("title"),
                "url": item.get("url"),
                "snippet": item.get("description"),
                "age_days": item.get("age")
            })

        return ToolResult({
            "provider": "brave",
            "query": query,
            "results": results
        })


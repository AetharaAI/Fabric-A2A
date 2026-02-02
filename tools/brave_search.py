import os
import httpx

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")

if not BRAVE_API_KEY:
    raise RuntimeError("BRAVE_API_KEY is not set")

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"

def brave_web_search(query: str, recency_days: int = 7, max_results: int = 5):
    headers = {
        "X-Subscription-Token": BRAVE_API_KEY,
        "Accept": "application/json"
    }

    params = {
        "q": query,
        "recency": recency_days,
        "domains": None
    }

    with httpx.Client(timeout=15.0) as client:
        r = client.get(BRAVE_ENDPOINT, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()

    results = []
    for item in data.get("web", {}).get("results", [])[:max_results]:
        results.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "snippet": item.get("description"),
            "age_days": item.get("age"),
        })

    return {
        "provider": "brave",
        "query": query,
        "results": results
    }

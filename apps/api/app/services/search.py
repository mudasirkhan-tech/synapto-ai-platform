"""Optional web search through a self-hosted SearXNG instance (no API key, no third-party AI service)."""
import httpx

from app.schemas import WebResult


class SearchError(Exception):
    pass


async def web_search(base_url: str, query: str, limit: int = 5) -> list[WebResult]:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            res = await client.get(
                f"{base_url.rstrip('/')}/search",
                params={"q": query, "format": "json"},
                headers={"Accept": "application/json"},
            )
            res.raise_for_status()
            data = res.json()
    except httpx.ConnectError as exc:
        raise SearchError("Cannot reach the search server. Is SearXNG running?") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise SearchError("The search server returned an error. Check that JSON output is enabled in SearXNG.") from exc

    results = []
    for item in data.get("results", []):
        url = str(item.get("url", ""))
        if url.startswith(("http://", "https://")):
            results.append(WebResult(title=str(item.get("title") or url)[:200], url=url, snippet=str(item.get("content") or "")[:400]))
        if len(results) >= limit:
            break
    return results

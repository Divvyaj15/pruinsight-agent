"""Multi-provider web search: Tavily (primary) → Serper (optional) → DuckDuckGo (free fallback).

Step 4 enhancement: keep research working when Tavily is down, rate-limited, or missing.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

SearchMode = Literal["web", "news"]

_tavily_client = None


@dataclass
class SearchHit:
    title: str
    url: str
    content: str
    provider: str
    score: Optional[float] = None
    published: str = ""


@dataclass
class SearchResponse:
    hits: list[SearchHit] = field(default_factory=list)
    providers_tried: list[str] = field(default_factory=list)
    provider_used: str = ""
    errors: list[str] = field(default_factory=list)


def _tavily_key() -> Optional[str]:
    return os.getenv("TAVILY_API_KEY")


def _serper_key() -> Optional[str]:
    return os.getenv("SERPER_API_KEY") or os.getenv("SERPER_KEY")


def provider_status() -> dict[str, bool]:
    """Which search backends are configured / available."""
    ddg_ok = True
    try:
        import ddgs  # noqa: F401
    except ImportError:
        try:
            import duckduckgo_search  # noqa: F401
        except ImportError:
            ddg_ok = False
    return {
        "tavily": bool(_tavily_key()),
        "serper": bool(_serper_key()),
        "duckduckgo": ddg_ok,
    }


def _search_tavily(query: str, max_results: int, mode: SearchMode) -> list[SearchHit]:
    from tavily import TavilyClient

    key = _tavily_key()
    if not key:
        raise ValueError("TAVILY_API_KEY not set")
    global _tavily_client
    if _tavily_client is None:
        _tavily_client = TavilyClient(api_key=key)

    kwargs: dict[str, Any] = {
        "max_results": max_results,
        "search_depth": "advanced" if mode == "web" else "basic",
    }
    if mode == "news":
        try:
            results = _tavily_client.search(
                query, topic="news", days=14, **kwargs
            )
        except TypeError:
            results = _tavily_client.search(
                f"{query} latest news India", max_results=max_results
            )
    else:
        results = _tavily_client.search(query, **kwargs)

    items = results.get("results") or []
    hits: list[SearchHit] = []
    for r in items:
        hits.append(
            SearchHit(
                title=r.get("title") or "Untitled",
                url=r.get("url") or "",
                content=(r.get("content") or "")[:600],
                provider="tavily",
                score=r.get("score") if isinstance(r.get("score"), (int, float)) else None,
                published=str(r.get("published_date") or r.get("publishedDate") or ""),
            )
        )
    return hits


def _search_serper(query: str, max_results: int, mode: SearchMode) -> list[SearchHit]:
    key = _serper_key()
    if not key:
        raise ValueError("SERPER_API_KEY not set")

    endpoint = (
        "https://google.serper.dev/news"
        if mode == "news"
        else "https://google.serper.dev/search"
    )
    resp = requests.post(
        endpoint,
        headers={"X-API-KEY": key, "Content-Type": "application/json"},
        json={"q": query, "num": max_results},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    hits: list[SearchHit] = []

    if mode == "news":
        rows = data.get("news") or []
        for r in rows[:max_results]:
            hits.append(
                SearchHit(
                    title=r.get("title") or "Untitled",
                    url=r.get("link") or "",
                    content=(r.get("snippet") or "")[:600],
                    provider="serper",
                    published=str(r.get("date") or ""),
                )
            )
    else:
        # organic results; optionally include knowledge graph snippet
        rows = data.get("organic") or []
        for r in rows[:max_results]:
            hits.append(
                SearchHit(
                    title=r.get("title") or "Untitled",
                    url=r.get("link") or "",
                    content=(r.get("snippet") or "")[:600],
                    provider="serper",
                    score=r.get("position"),
                )
            )
        answer = data.get("answerBox") or {}
        if answer.get("answer") or answer.get("snippet"):
            hits.insert(
                0,
                SearchHit(
                    title=answer.get("title") or "Answer box",
                    url=answer.get("link") or "",
                    content=(answer.get("answer") or answer.get("snippet") or "")[:600],
                    provider="serper",
                ),
            )
    return hits[:max_results]


def _search_duckduckgo(query: str, max_results: int, mode: SearchMode) -> list[SearchHit]:
    """Free fallback — no API key. Uses `ddgs` (or legacy duckduckgo_search)."""
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # type: ignore
        except ImportError as e:
            raise ImportError(
                "Install ddgs for DuckDuckGo fallback: pip install ddgs"
            ) from e

    hits: list[SearchHit] = []
    with DDGS() as ddgs:
        if mode == "news":
            try:
                rows = list(ddgs.news(query, max_results=max_results))
            except Exception:
                rows = list(ddgs.text(f"{query} latest news", max_results=max_results))
            for r in rows[:max_results]:
                hits.append(
                    SearchHit(
                        title=r.get("title") or "Untitled",
                        url=r.get("url") or r.get("href") or "",
                        content=(r.get("body") or r.get("excerpt") or "")[:600],
                        provider="duckduckgo",
                        published=str(r.get("date") or ""),
                    )
                )
        else:
            rows = list(ddgs.text(query, max_results=max_results))
            for r in rows[:max_results]:
                hits.append(
                    SearchHit(
                        title=r.get("title") or "Untitled",
                        url=r.get("href") or r.get("url") or "",
                        content=(r.get("body") or "")[:600],
                        provider="duckduckgo",
                    )
                )
    return hits


def multi_search(
    query: str,
    *,
    max_results: int = 6,
    mode: SearchMode = "web",
    prefer: Optional[list[str]] = None,
) -> SearchResponse:
    """Try providers in order until one returns hits.

    Default order: tavily → serper → duckduckgo
    """
    order = prefer or ["tavily", "serper", "duckduckgo"]
    out = SearchResponse()
    runners = {
        "tavily": _search_tavily,
        "serper": _search_serper,
        "duckduckgo": _search_duckduckgo,
    }

    for name in order:
        fn = runners.get(name)
        if not fn:
            continue
        out.providers_tried.append(name)
        try:
            hits = fn(query, max_results, mode)
            if hits:
                out.hits = hits
                out.provider_used = name
                return out
            out.errors.append(f"{name}: no results")
        except Exception as e:
            out.errors.append(f"{name}: {e}")

    return out


def format_search_response(resp: SearchResponse, *, header: str = "") -> str:
    if not resp.hits:
        tried = ", ".join(resp.providers_tried) or "none"
        errs = "; ".join(resp.errors) if resp.errors else "no details"
        return (
            f"No search results found.\n"
            f"Providers tried: {tried}\n"
            f"Errors: {errs}"
        )

    lines: list[str] = []
    if header:
        lines.append(header)
    lines.append(
        f"Search provider used: **{resp.provider_used}** "
        f"(tried: {', '.join(resp.providers_tried)})"
    )
    if resp.errors:
        lines.append("Fallback notes: " + "; ".join(resp.errors))
    lines.append("")

    for i, h in enumerate(resp.hits, 1):
        score_s = f" (score {h.score})" if h.score is not None else ""
        pub = f" | {h.published}" if h.published else ""
        lines.append(
            f"{i}. {h.title}{score_s}{pub}\n"
            f"   {h.content}\n"
            f"   Source: {h.url}\n"
            f"   via: {h.provider}"
        )
    return "\n\n".join(lines)


def search_as_dicts(
    query: str,
    *,
    max_results: int = 6,
    mode: SearchMode = "web",
) -> tuple[list[dict[str, Any]], str, list[str]]:
    """Convenience for tools that need {title,url,content} lists.

    Returns (items, provider_used, errors).
    """
    resp = multi_search(query, max_results=max_results, mode=mode)
    items = [
        {
            "title": h.title,
            "url": h.url,
            "content": h.content,
            "score": h.score,
            "published_date": h.published,
            "provider": h.provider,
        }
        for h in resp.hits
    ]
    return items, resp.provider_used, resp.errors

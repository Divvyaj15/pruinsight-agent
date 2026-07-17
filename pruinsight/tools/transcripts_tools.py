"""Earnings call transcript discovery, ingest (PDF/HTML), and BM25 RAG.

Step 6: management tone / Q&A color for MF desk research.
"""

from __future__ import annotations

import re
from html import unescape
from typing import Optional
from urllib.parse import urlparse

import requests
from langchain_core.tools import tool

from pruinsight.rag.store import Chunk, get_transcript_store
from pruinsight.tools.filings_tools import download_pdf, extract_pdf_bytes
from pruinsight.tools.search_providers import search_as_dicts

_SESSION = requests.Session()
_SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
    }
)

# Prefer IR / transcript hosts when ranking
_TRANSCRIPT_BOOST = (
    "earnings",
    "transcript",
    "conference-call",
    "concall",
    "investor",
    "hdfcbank.com",
    "icicibank.com",
    "reliancedigital",
    "ril.com",
    "tcs.com",
    "infosys.com",
    "bseindia.com",
    "nseindia.com",
    "nsearchives",
    "moneycontrol.com",
    "screener.in",
    "trendlyne",
    "alphastreet",
    "seekingalpha",
    "fool.com",
)


def _boost(url: str, title: str = "") -> int:
    u = (url or "").lower()
    t = (title or "").lower()
    score = 0
    if ".pdf" in u:
        score += 4
    for k in _TRANSCRIPT_BOOST:
        if k in u or k in t:
            score += 2
    if "transcript" in u or "transcript" in t:
        score += 5
    if "earnings" in t or "earnings" in u:
        score += 2
    if "concall" in u or "conference call" in t:
        score += 3
    return score


def _html_to_text(html: str) -> str:
    """Lightweight HTML → text (no BS4 required)."""
    if not html:
        return ""
    # drop scripts/styles
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<noscript[^>]*>.*?</noscript>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"(?i)</div>", "\n", text)
    text = re.sub(r"(?i)</h[1-6]>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def _chunk_plain(
    text: str,
    *,
    source_url: str,
    title: str,
    chunk_size: int = 1200,
    overlap: int = 150,
) -> list[Chunk]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    chunks: list[Chunk] = []
    i = 0
    n = 0
    while i < len(text):
        piece = text[i : i + chunk_size]
        n += 1
        chunks.append(
            Chunk(
                chunk_id=f"tr-{hash(source_url) & 0xfffffff:x}-{n}",
                text=piece,
                source_url=source_url,
                title=title,
                page_start=n,
                page_end=n,
                meta={"doc_type": "transcript"},
            )
        )
        if i + chunk_size >= len(text):
            break
        i += max(chunk_size - overlap, 1)
    return chunks


def _fetch_html_text(url: str, timeout: int = 40) -> tuple[str, str]:
    resp = _SESSION.get(url, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    ctype = (resp.headers.get("Content-Type") or "").lower()
    data = resp.content
    if "pdf" in ctype or data[:5].startswith(b"%PDF"):
        raise ValueError("URL is PDF — use PDF ingest path")
    # encoding
    text = data.decode(resp.encoding or "utf-8", errors="replace")
    if "html" not in ctype and "<html" not in text[:500].lower():
        # plain text page
        return text, urlparse(url).path.split("/")[-1] or url
    plain = _html_to_text(text)
    title_m = re.search(r"(?is)<title[^>]*>(.*?)</title>", text)
    title = _html_to_text(title_m.group(1)) if title_m else urlparse(url).path
    return plain, title or "transcript"


@tool
def search_earnings_transcripts(query: str) -> str:
    """Search for earnings call / conference call transcripts for a company.

    Pass company name and/or NSE symbol, e.g. 'HDFC Bank HDFCBANK earnings call transcript'.
    Prefers IR pages, exchange attachments, and known transcript hosts.
    After finding a good URL, call ingest_transcript_document.
    """
    try:
        q = (query or "").strip()
        if not q:
            return "Provide a company name or symbol."
        searches = [
            f"{q} earnings call transcript",
            f"{q} conference call transcript Q1 OR Q2 OR Q3 OR Q4",
            f"{q} earnings concall transcript PDF India",
        ]
        seen: set[str] = set()
        ranked: list[tuple[int, dict]] = []
        providers: list[str] = []
        for sq in searches:
            items, provider, _errs = search_as_dicts(sq, max_results=6, mode="web")
            if provider:
                providers.append(provider)
            for r in items:
                url = (r.get("url") or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                score = _boost(url, r.get("title") or "")
                ranked.append((score, r))
        ranked.sort(key=lambda x: x[0], reverse=True)
        if not ranked:
            return "No earnings transcript results found (Tavily/Serper/DuckDuckGo)."

        lines = [
            "Earnings transcript search results (ranked):",
            f"Search providers: {', '.join(dict.fromkeys(providers)) or 'n/a'}",
            "",
        ]
        for i, (score, r) in enumerate(ranked[:10], 1):
            title = r.get("title") or "Untitled"
            url = r.get("url") or ""
            content = (r.get("content") or "")[:280]
            pdf = " [PDF]" if ".pdf" in url.lower() else ""
            via = r.get("provider") or ""
            lines.append(
                f"{i}. {title}{pdf} (score={score})\n"
                f"   {content}\n   URL: {url}"
                + (f"\n   via: {via}" if via else "")
            )
        lines.append(
            "\nNext: ingest_transcript_document(url) then query_transcripts_rag(question)."
        )
        return "\n\n".join(lines)
    except Exception as e:
        return f"Transcript search failed: {e}"


@tool
def ingest_transcript_document(url: str, title: str = "") -> str:
    """Download an earnings transcript (PDF or HTML page), extract text, add to transcript RAG store.

    Use after search_earnings_transcripts. Prefer full transcript PDFs or IR HTML pages.
    """
    try:
        url = (url or "").strip()
        if not url.startswith("http"):
            return "Invalid URL."
        store = get_transcript_store()
        doc_title = title.strip() or urlparse(url).path.split("/")[-1] or url

        # Prefer PDF path when obvious
        is_pdf_url = ".pdf" in url.lower()
        chunks: list[Chunk] = []
        pages = 0
        chars = 0

        if is_pdf_url:
            data = download_pdf(url)
            chunks, pages, chars = extract_pdf_bytes(
                data, source_url=url, title=doc_title, max_pages=50
            )
            for c in chunks:
                c.meta["doc_type"] = "transcript"
        else:
            try:
                data = download_pdf(url)
                if data[:5].startswith(b"%PDF"):
                    chunks, pages, chars = extract_pdf_bytes(
                        data, source_url=url, title=doc_title, max_pages=50
                    )
                    for c in chunks:
                        c.meta["doc_type"] = "transcript"
                else:
                    raise ValueError("not pdf")
            except Exception:
                plain, html_title = _fetch_html_text(url)
                if len(plain) < 400:
                    return (
                        f"Fetched page but text too short ({len(plain)} chars) — "
                        f"may be paywalled/JS-only: {url}"
                    )
                doc_title = title.strip() or html_title or doc_title
                # Cap very long HTML transcripts
                plain = plain[:120_000]
                chunks = _chunk_plain(plain, source_url=url, title=doc_title)
                pages = 1
                chars = len(plain)

        if not chunks:
            return f"No text extracted from {url}"
        n = store.add_chunks(chunks)
        store.register_source(doc_title, url, pages, chars)
        return (
            f"Ingested transcript '{doc_title}' from {url}\n"
            f"Pages/sections: {pages}, chars: {chars}, chunks: {n}\n"
            f"{store.summary()}"
        )
    except Exception as e:
        return f"Transcript ingest failed for {url}: {e}"


@tool
def query_transcripts_rag(question: str, k: int = 6) -> str:
    """Retrieve relevant excerpts from ingested earnings call transcripts (BM25 RAG).

    Ask about guidance, margins, asset quality, capex, management tone, Q&A risks, etc.
    """
    try:
        store = get_transcript_store()
        hits = store.query(question, k=max(1, min(int(k or 6), 12)))
        if not hits:
            return (
                "No transcripts in the RAG store. "
                "Use search_earnings_transcripts then ingest_transcript_document first."
            )
        blocks = [f"Transcript RAG hits for: {question}", store.summary(), ""]
        for i, c in enumerate(hits, 1):
            blocks.append(
                f"--- Excerpt {i} | {c.title} | chunk {c.page_start} ---\n"
                f"{c.text}\nSource: {c.source_url}"
            )
        return "\n\n".join(blocks)
    except Exception as e:
        return f"Transcript RAG failed: {e}"


@tool
def list_ingested_transcripts() -> str:
    """List earnings transcripts currently loaded in the RAG store for this run."""
    return get_transcript_store().summary()


TRANSCRIPT_TOOLS = [
    search_earnings_transcripts,
    ingest_transcript_document,
    query_transcripts_rag,
    list_ingested_transcripts,
]


def programmatic_transcripts_brief(
    query: str,
    symbols: list[str] | None = None,
    max_docs: int = 2,
) -> str:
    """Deterministic search → ingest → RAG path for the transcripts agent."""
    store = get_transcript_store()
    store.clear()

    symbols = symbols or []
    seeds = []
    if symbols:
        for s in symbols[:3]:
            seeds.append(f"{s} earnings call transcript India")
            seeds.append(f"{s} conference call transcript")
    seeds.append(f"{query} earnings call transcript")
    # unique
    seen_q: set[str] = set()
    queries = []
    for s in seeds:
        if s not in seen_q:
            seen_q.add(s)
            queries.append(s)

    parts: list[str] = ["=== Earnings transcript pipeline ===", ""]
    all_urls: list[tuple[int, str, str]] = []  # score, url, title
    providers: list[str] = []

    for sq in queries[:4]:
        raw = search_earnings_transcripts.invoke({"query": sq})
        parts.append(raw)
        parts.append("")
        # parse URLs from output
        for m in re.finditer(r"URL:\s*(\S+)", raw):
            url = m.group(1).strip()
            all_urls.append((_boost(url), url, ""))
        if "Search providers:" in raw:
            for line in raw.splitlines():
                if line.startswith("Search providers:"):
                    providers.append(line.split(":", 1)[-1].strip())

    # rank unique urls
    by_url: dict[str, int] = {}
    for score, url, _ in all_urls:
        by_url[url] = max(by_url.get(url, 0), score)
    ordered = sorted(by_url.items(), key=lambda x: x[1], reverse=True)

    ingest_logs = []
    ingested = 0
    for url, score in ordered:
        if ingested >= max_docs:
            break
        # skip obvious non-transcript junk
        ul = url.lower()
        if any(x in ul for x in ("youtube.com", "twitter.com", "x.com", "facebook.com")):
            continue
        result = ingest_transcript_document.invoke({"url": url, "title": ""})
        ingest_logs.append(result)
        if result.startswith("Ingested"):
            ingested += 1

    parts.append("=== Ingest log ===")
    parts.append("\n\n".join(ingest_logs) if ingest_logs else "No documents ingested.")
    parts.append("")

    if ingested:
        parts.append("=== Transcript RAG ===")
        for q in (
            query,
            "management guidance outlook growth margins",
            "risks challenges asset quality competition regulation",
            "capital expenditure investment strategy Q&A highlights",
            "loan growth deposits NIMs" if any(
                s in ("HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK")
                for s in symbols
            )
            else "revenue profit demand commentary",
        ):
            parts.append(query_transcripts_rag.invoke({"question": q, "k": 4}))
            parts.append("")
    else:
        parts.append(
            "No transcript text ingested. "
            "May be paywalled, JS-only, or not found — rely on filings/news instead."
        )

    if providers:
        parts.append(f"Providers seen: {', '.join(dict.fromkeys(providers))}")
    return "\n".join(parts)

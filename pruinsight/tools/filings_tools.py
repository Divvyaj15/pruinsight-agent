"""SEBI / exchange / company filing discovery, PDF ingest, and RAG query tools."""

from __future__ import annotations

import io
import os
import re
from typing import Optional
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from langchain_core.tools import tool
from pypdf import PdfReader
from tavily import TavilyClient

from pruinsight.rag.store import Chunk, get_filings_store

load_dotenv()

_tavily: Optional[TavilyClient] = None

# Prefer primary-market / regulator domains when ranking results
_PREFERRED_DOMAINS = (
    "bseindia.com",
    "nseindia.com",
    "sebi.gov.in",
    "archives.nseindia.com",
    "www1.nseindia.com",
    "linkintimes.co.in",
    "investors.",  # common IR subdomain pattern
)

_SESSION = requests.Session()
_SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
)


def _get_tavily() -> TavilyClient:
    global _tavily
    if _tavily is None:
        key = os.getenv("TAVILY_API_KEY")
        if not key:
            raise ValueError("TAVILY_API_KEY is not set")
        _tavily = TavilyClient(api_key=key)
    return _tavily


def _domain_boost(url: str) -> int:
    host = urlparse(url).netloc.lower()
    path = urlparse(url).path.lower()
    score = 0
    for d in _PREFERRED_DOMAINS:
        if d in host or d in url.lower():
            score += 5
    if path.endswith(".pdf") or ".pdf" in path:
        score += 4
    for kw in ("annual", "result", "investor", "presentation", "filing", "sebi", "quarterly"):
        if kw in url.lower():
            score += 1
    return score


def _chunk_text(
    text: str,
    *,
    source_url: str,
    title: str,
    page_start: int,
    page_end: int,
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
                chunk_id=f"{hash(source_url) & 0xfffffff:x}-{page_start}-{n}",
                text=piece,
                source_url=source_url,
                title=title,
                page_start=page_start,
                page_end=page_end,
            )
        )
        if i + chunk_size >= len(text):
            break
        i += max(chunk_size - overlap, 1)
    return chunks


def extract_pdf_bytes(
    data: bytes,
    *,
    source_url: str,
    title: str,
    max_pages: int = 40,
) -> tuple[list[Chunk], int, int]:
    """Return (chunks, page_count_used, char_count)."""
    reader = PdfReader(io.BytesIO(data))
    total_pages = len(reader.pages)
    # Prefer front matter (MD&A, highlights) — first max_pages
    use_pages = min(total_pages, max_pages)
    all_chunks: list[Chunk] = []
    chars = 0
    for idx in range(use_pages):
        try:
            page_text = reader.pages[idx].extract_text() or ""
        except Exception:
            page_text = ""
        page_text = page_text.strip()
        if not page_text:
            continue
        chars += len(page_text)
        all_chunks.extend(
            _chunk_text(
                page_text,
                source_url=source_url,
                title=title,
                page_start=idx + 1,
                page_end=idx + 1,
            )
        )
    return all_chunks, use_pages, chars


def download_pdf(url: str, timeout: int = 45) -> bytes:
    resp = _SESSION.get(url, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    content_type = (resp.headers.get("Content-Type") or "").lower()
    data = resp.content
    if "pdf" not in content_type and not data[:5].startswith(b"%PDF"):
        # Some IR servers mislabel PDFs; only reject if clearly HTML
        head = data[:200].lower()
        if b"<html" in head or b"<!doctype" in head:
            raise ValueError(f"URL did not return a PDF (content-type={content_type})")
    if not data:
        raise ValueError("Empty response body")
    return data


@tool
def search_company_filings(query: str) -> str:
    """Search for company primary-source documents: annual reports, quarterly results,
    investor presentations, BSE/NSE announcements, SEBI-related filings (PDF links preferred).

    Pass company name and/or NSE symbol, e.g. 'HDFC Bank HDFCBANK annual report'.
    """
    try:
        client = _get_tavily()
        # Two complementary searches improve hit rate on exchange domains
        queries = [
            f"{query} annual report OR quarterly results PDF India",
            f"{query} investor presentation OR financial results site:bseindia.com OR site:nseindia.com OR site:sebi.gov.in",
        ]
        seen: set[str] = set()
        ranked: list[tuple[int, dict]] = []
        for q in queries:
            try:
                results = client.search(q, max_results=6, search_depth="advanced")
            except Exception:
                results = client.search(q, max_results=6)
            for r in results.get("results") or []:
                url = (r.get("url") or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                ranked.append((_domain_boost(url), r))

        ranked.sort(key=lambda x: x[0], reverse=True)
        if not ranked:
            return "No filing-related search results found."

        lines = ["Filing / primary-source search results (ranked):"]
        for i, (boost, r) in enumerate(ranked[:10], 1):
            title = r.get("title") or "Untitled"
            url = r.get("url") or ""
            content = (r.get("content") or "")[:280]
            pdf_flag = " [PDF likely]" if ".pdf" in url.lower() else ""
            lines.append(
                f"{i}. {title}{pdf_flag} (score={boost})\n"
                f"   {content}\n   URL: {url}"
            )
        lines.append(
            "\nTip: Call ingest_filing_pdf on the most relevant PDF URLs, "
            "then query_filings_rag for excerpts."
        )
        return "\n\n".join(lines)
    except Exception as e:
        return f"Filing search failed: {e}"


@tool
def ingest_filing_pdf(url: str, title: str = "") -> str:
    """Download a PDF filing from a URL, extract text, and add it to the RAG store.

    Use after search_company_filings. Prefer BSE/NSE/SEBI/company IR PDF links.
    """
    try:
        url = (url or "").strip()
        if not url.startswith("http"):
            return "Invalid URL."
        data = download_pdf(url)
        doc_title = title.strip() or urlparse(url).path.split("/")[-1] or url
        chunks, pages, chars = extract_pdf_bytes(
            data, source_url=url, title=doc_title, max_pages=40
        )
        if not chunks:
            return f"Downloaded PDF but extracted no text (may be scanned images): {url}"
        store = get_filings_store()
        n = store.add_chunks(chunks)
        store.register_source(doc_title, url, pages, chars)
        return (
            f"Ingested '{doc_title}' from {url}\n"
            f"Pages used: {pages}, chars: {chars}, chunks added: {n}\n"
            f"{store.summary()}"
        )
    except Exception as e:
        return f"Ingest failed for {url}: {e}"


@tool
def query_filings_rag(question: str, k: int = 6) -> str:
    """Retrieve the most relevant excerpts from ingested company filings (BM25 RAG).

    Call after ingest_filing_pdf. Ask specific questions, e.g.
    'What did management say about loan growth and NIMs?' or
    'Key risks disclosed in the annual report'.
    """
    try:
        store = get_filings_store()
        hits = store.query(question, k=max(1, min(int(k or 6), 12)))
        if not hits:
            return (
                "No filings in the RAG store yet. "
                "Use search_company_filings then ingest_filing_pdf first."
            )
        blocks = [f"RAG hits for: {question}", store.summary(), ""]
        for i, c in enumerate(hits, 1):
            blocks.append(
                f"--- Excerpt {i} | {c.title} | p.{c.page_start} ---\n"
                f"{c.text}\n"
                f"Source: {c.source_url}"
            )
        return "\n\n".join(blocks)
    except Exception as e:
        return f"RAG query failed: {e}"


@tool
def list_ingested_filings() -> str:
    """List PDFs currently loaded in the filings RAG store for this run."""
    return get_filings_store().summary()


FILINGS_TOOLS = [
    search_company_filings,
    ingest_filing_pdf,
    query_filings_rag,
    list_ingested_filings,
]


def programmatic_filings_brief(
    query: str,
    symbols: list[str] | None = None,
    max_pdfs: int = 2,
) -> str:
    """Deterministic search → ingest → RAG path (used by filings agent).

    More reliable than relying solely on the LLM to choose tools.
    """
    store = get_filings_store()
    store.clear()

    names = symbols or []
    seed = " ".join(names) if names else query
    search_q = f"{seed} {query}".strip()

    search_out = search_company_filings.invoke({"query": search_q})
    # Parse URLs from search output
    urls = re.findall(r"URL:\s*(\S+)", search_out)
    # Prefer PDFs
    pdfs = [u for u in urls if ".pdf" in u.lower()]
    others = [u for u in urls if u not in pdfs]
    ordered = pdfs + others

    ingest_logs: list[str] = []
    ingested = 0
    for url in ordered:
        if ingested >= max_pdfs:
            break
        # Skip obvious non-document pages when we still have PDF candidates later
        if ".pdf" not in url.lower() and ingested == 0 and pdfs:
            continue
        if ".pdf" not in url.lower() and ingested > 0:
            continue
        result = ingest_filing_pdf.invoke({"url": url, "title": ""})
        ingest_logs.append(result)
        if result.startswith("Ingested"):
            ingested += 1

    if ingested == 0:
        # Try any remaining URLs that might still be PDFs without extension
        for url in ordered[:3]:
            result = ingest_filing_pdf.invoke({"url": url, "title": ""})
            ingest_logs.append(result)
            if result.startswith("Ingested"):
                ingested += 1
                if ingested >= max_pdfs:
                    break

    rag_questions = [
        query,
        "key financial highlights revenue profit growth margins",
        "risks risk factors outlook guidance management commentary",
        "capital adequacy asset quality deposits advances" if any(
            "bank" in (s or "").lower() or s in ("HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK")
            for s in names
        ) else "strategy outlook capital allocation",
    ]
    rag_blocks = []
    for q in rag_questions:
        rag_blocks.append(query_filings_rag.invoke({"question": q, "k": 4}))

    return (
        "=== Filing search ===\n"
        f"{search_out}\n\n"
        "=== Ingest log ===\n"
        + "\n\n".join(ingest_logs[:6])
        + "\n\n=== RAG excerpts ===\n"
        + "\n\n".join(rag_blocks)
    )

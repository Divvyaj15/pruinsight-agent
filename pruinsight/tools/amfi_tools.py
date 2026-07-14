"""AMFI mutual fund NAV data + fund factsheet discovery / RAG tools."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from langchain_core.tools import tool
from tavily import TavilyClient

from pruinsight.rag.store import Chunk, get_factsheet_store
from pruinsight.tools.filings_tools import download_pdf, extract_pdf_bytes

load_dotenv()

AMFI_NAV_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"

_SESSION = requests.Session()
_SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
    }
)

_tavily: Optional[TavilyClient] = None

# Cache NAV universe in memory (refreshed periodically)
_NAV_CACHE: list["SchemeRow"] = []
_NAV_CACHE_TS: float = 0.0
_NAV_CACHE_TTL = 60 * 60  # 1 hour
_NAV_CACHE_META: dict = {}


@dataclass
class SchemeRow:
    code: str
    isin_growth: str
    isin_div: str
    name: str
    nav: str
    date: str
    category: str
    amc: str


def _get_tavily() -> TavilyClient:
    global _tavily
    if _tavily is None:
        key = os.getenv("TAVILY_API_KEY")
        if not key:
            raise ValueError("TAVILY_API_KEY is not set")
        _tavily = TavilyClient(api_key=key)
    return _tavily


def _parse_nav_text(text: str) -> list[SchemeRow]:
    rows: list[SchemeRow] = []
    category = ""
    amc = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # Header
        if line.lower().startswith("scheme code"):
            continue
        # Category banner: Open Ended Schemes(...)
        if line.startswith("Open Ended Schemes") or line.startswith("Close Ended Schemes"):
            category = line
            continue
        # Data row has semicolons and starts with digits
        if ";" in line and re.match(r"^\d+;", line):
            parts = line.split(";")
            if len(parts) < 6:
                continue
            rows.append(
                SchemeRow(
                    code=parts[0].strip(),
                    isin_growth=parts[1].strip(),
                    isin_div=parts[2].strip(),
                    name=parts[3].strip(),
                    nav=parts[4].strip(),
                    date=parts[5].strip(),
                    category=category,
                    amc=amc,
                )
            )
            continue
        # AMC name lines (no semicolons, not a category)
        if ";" not in line and "Schemes(" not in line:
            amc = line
    return rows


def load_amfi_schemes(force: bool = False) -> list[SchemeRow]:
    """Download/parse AMFI NAVAll.txt with in-process cache."""
    global _NAV_CACHE, _NAV_CACHE_TS, _NAV_CACHE_META
    now = time.time()
    if (
        not force
        and _NAV_CACHE
        and (now - _NAV_CACHE_TS) < _NAV_CACHE_TTL
    ):
        return _NAV_CACHE

    resp = _SESSION.get(AMFI_NAV_URL, timeout=90)
    resp.raise_for_status()
    # AMFI file is typically latin-1 / cp1252 friendly
    text = resp.content.decode("utf-8", errors="replace")
    rows = _parse_nav_text(text)
    _NAV_CACHE = rows
    _NAV_CACHE_TS = now
    _NAV_CACHE_META = {
        "url": AMFI_NAV_URL,
        "count": len(rows),
        "bytes": len(resp.content),
        "fetched_ts": now,
    }
    return rows


def _score_scheme(row: SchemeRow, tokens: list[str]) -> float:
    name_l = row.name.lower()
    cat_l = (row.category or "").lower()
    amc_l = (row.amc or "").lower()
    hay = f"{name_l} {cat_l} {amc_l}"
    score = 0.0
    for t in tokens:
        if t in name_l:
            score += 3.0
        elif t in amc_l:
            score += 1.5
        elif t in cat_l:
            score += 1.0
        elif t in hay:
            score += 0.5
    # Prefer growth plans for desk comparison
    if "growth" in name_l:
        score += 1.2
    if "direct" in name_l:
        score += 0.4
    # Deprioritize IDCW/dividend noise slightly
    if "idcw" in name_l or "dividend" in name_l:
        score -= 0.8
    return score


def _format_row(row: SchemeRow) -> str:
    return (
        f"Code: {row.code} | NAV: {row.nav} ({row.date})\n"
        f"Scheme: {row.name}\n"
        f"AMC: {row.amc or 'N/A'}\n"
        f"Category: {row.category or 'N/A'}\n"
        f"ISIN (growth/div payout): {row.isin_growth or '-'} | "
        f"ISIN (div reinvest): {row.isin_div or '-'}"
    )


@tool
def search_amfi_schemes(query: str, limit: int = 8) -> str:
    """Search Indian mutual fund schemes in the official AMFI NAVAll universe.

    Pass keywords like 'HDFC Flexi Cap Growth', 'ICICI Prudential Bluechip',
    'large cap direct growth', 'banking sector fund'.
    Returns scheme code, name, latest NAV, date, AMC, and AMFI category banner.
    """
    try:
        q = (query or "").strip()
        if not q:
            return "Provide a scheme name or keywords."
        limit = max(1, min(int(limit or 8), 20))
        tokens = [t for t in re.findall(r"[a-zA-Z0-9]+", q.lower()) if len(t) > 1]
        schemes = load_amfi_schemes()
        ranked = sorted(
            schemes,
            key=lambda r: _score_scheme(r, tokens),
            reverse=True,
        )
        top = [r for r in ranked if _score_scheme(r, tokens) > 0][:limit]
        if not top:
            return f"No AMFI schemes matched '{q}'. Try AMC + category + Growth."
        lines = [
            f"AMFI scheme search for '{q}' (source: {AMFI_NAV_URL})",
            f"Universe size: {_NAV_CACHE_META.get('count', len(schemes))} schemes",
            "",
        ]
        for i, r in enumerate(top, 1):
            lines.append(f"--- Match {i} (score≈{_score_scheme(r, tokens):.1f}) ---")
            lines.append(_format_row(r))
            lines.append("")
        return "\n".join(lines)
    except Exception as e:
        return f"AMFI search failed: {e}"


@tool
def get_amfi_nav(scheme_code_or_name: str) -> str:
    """Get latest AMFI NAV for a scheme by scheme code (e.g. '120503') or exact-ish name.

    Prefer numeric scheme codes from search_amfi_schemes results.
    """
    try:
        key = (scheme_code_or_name or "").strip()
        if not key:
            return "Provide a scheme code or name."
        schemes = load_amfi_schemes()
        if key.isdigit():
            hits = [r for r in schemes if r.code == key]
        else:
            kl = key.lower()
            hits = [r for r in schemes if kl in r.name.lower()]
            hits = sorted(hits, key=lambda r: _score_scheme(r, kl.split()), reverse=True)[:5]
        if not hits:
            return f"No AMFI NAV found for '{key}'."
        lines = [f"AMFI NAV lookup for '{key}' (source: {AMFI_NAV_URL})", ""]
        for r in hits[:5]:
            lines.append(_format_row(r))
            lines.append("")
        return "\n".join(lines)
    except Exception as e:
        return f"AMFI NAV lookup failed: {e}"


@tool
def list_amfi_categories(keyword: str = "") -> str:
    """List AMFI open/close ended category banners (optionally filter by keyword).

    Examples: keyword='Large Cap', 'Flexi', 'Sectoral', 'Index'.
    """
    try:
        schemes = load_amfi_schemes()
        cats: dict[str, int] = {}
        for r in schemes:
            c = r.category or "(unknown)"
            cats[c] = cats.get(c, 0) + 1
        items = sorted(cats.items(), key=lambda x: x[0])
        kw = (keyword or "").strip().lower()
        if kw:
            items = [(c, n) for c, n in items if kw in c.lower()]
        if not items:
            return f"No categories matched '{keyword}'."
        lines = [f"AMFI categories (filter='{keyword or 'ALL'}'):", ""]
        for c, n in items[:40]:
            lines.append(f"- {c}  ({n} scheme rows)")
        return "\n".join(lines)
    except Exception as e:
        return f"AMFI category list failed: {e}"


@tool
def search_related_equity_funds(theme: str, limit: int = 8) -> str:
    """Find equity-oriented AMFI schemes related to a stock/sector theme for MF desk context.

    Examples: theme='large cap', 'banking HDFC', 'ICICI Prudential flexi cap',
    'IT sector', 'index nifty 50'.
    Prefers Growth plans.
    """
    try:
        theme = (theme or "").strip()
        if not theme:
            return "Provide a theme (e.g. large cap, banking, flexi cap)."
        limit = max(1, min(int(limit or 8), 15))
        tokens = [t for t in re.findall(r"[a-zA-Z0-9]+", theme.lower()) if len(t) > 1]
        # Bias toward equity-ish category words if user only passes a stock theme
        extra = []
        joined = " ".join(tokens)
        if any(x in joined for x in ("bank", "hdfc", "icici", "axis", "kotak", "sbi")):
            extra += ["banking", "financial", "equity"]
        if any(x in joined for x in ("it", "infosys", "tcs", "tech", "hcl", "wipro")):
            extra += ["technology", "digital", "equity"]
        if "large" in joined or "bluechip" in joined:
            extra += ["large", "cap"]
        tokens = list(dict.fromkeys(tokens + extra))

        schemes = load_amfi_schemes()
        # Prefer equity / hybrid equity categories
        def is_equityish(r: SchemeRow) -> bool:
            c = (r.category or "").lower()
            n = r.name.lower()
            return any(
                k in c or k in n
                for k in (
                    "equity",
                    "large cap",
                    "mid cap",
                    "small cap",
                    "flexi",
                    "multi cap",
                    "index",
                    "sectoral",
                    "thematic",
                    "elss",
                    "value",
                    "focused",
                    "dividend yield",
                )
            )

        candidates = [r for r in schemes if is_equityish(r)] or schemes
        ranked = sorted(
            candidates,
            key=lambda r: _score_scheme(r, tokens),
            reverse=True,
        )
        top = [r for r in ranked if _score_scheme(r, tokens) > 0][:limit]
        # De-duplicate near-identical names keeping growth direct when possible
        seen = set()
        deduped: list[SchemeRow] = []
        for r in top:
            key = re.sub(r"\s+", " ", r.name.lower())
            key = re.sub(r"(direct|regular|plan|option|growth|idcw|dividend)", "", key)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(r)
            if len(deduped) >= limit:
                break

        if not deduped:
            return f"No related equity funds found for theme '{theme}'."
        lines = [
            f"Related equity-oriented schemes for theme '{theme}'",
            f"Source: {AMFI_NAV_URL}",
            "",
        ]
        for i, r in enumerate(deduped, 1):
            lines.append(f"{i}. {_format_row(r)}")
            lines.append("")
        return "\n".join(lines)
    except Exception as e:
        return f"Related fund search failed: {e}"


@tool
def search_fund_factsheet(query: str) -> str:
    """Search the web for mutual fund factsheet / SID / portfolio PDF documents.

    Pass scheme or AMC name, e.g. 'ICICI Prudential Bluechip Fund factsheet PDF'.
    Prefer official AMC domains. After finding a PDF URL, call ingest_fund_factsheet_pdf.
    """
    try:
        q = (query or "").strip()
        if not q:
            return "Provide a fund/AMC name."
        client = _get_tavily()
        searches = [
            f"{q} mutual fund factsheet PDF",
            f"{q} scheme factsheet site:.in filetype:pdf",
        ]
        seen: set[str] = set()
        ranked: list[tuple[int, dict]] = []
        for sq in searches:
            try:
                results = client.search(sq, max_results=5, search_depth="basic")
            except Exception:
                results = client.search(sq, max_results=5)
            for r in results.get("results") or []:
                url = (r.get("url") or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                score = 0
                ul = url.lower()
                if ".pdf" in ul:
                    score += 5
                for d in (
                    "icicipruamc",
                    "hdfcfund",
                    "sbimf",
                    "axismf",
                    "kotakmf",
                    "nipponindia",
                    "utimf",
                    "adityabirlacapital",
                    "dspim",
                    "motilaloswalmf",
                    "amfiindia",
                    "sebi.gov",
                ):
                    if d in ul:
                        score += 4
                if "factsheet" in ul or "fact-sheet" in ul or "factsheet" in (r.get("title") or "").lower():
                    score += 3
                if "sid" in ul or "portfolio" in ul:
                    score += 1
                ranked.append((score, r))
        ranked.sort(key=lambda x: x[0], reverse=True)
        if not ranked:
            return "No factsheet results found."
        lines = ["Fund factsheet / document search results:"]
        for i, (score, r) in enumerate(ranked[:8], 1):
            title = r.get("title") or "Untitled"
            url = r.get("url") or ""
            snippet = (r.get("content") or "")[:240]
            pdf = " [PDF likely]" if ".pdf" in url.lower() else ""
            lines.append(
                f"{i}. {title}{pdf} (score={score})\n   {snippet}\n   URL: {url}"
            )
        lines.append(
            "\nNext: ingest_fund_factsheet_pdf(url) then query_factsheet_rag(question)."
        )
        return "\n\n".join(lines)
    except Exception as e:
        return f"Factsheet search failed: {e}"


@tool
def ingest_fund_factsheet_pdf(url: str, title: str = "") -> str:
    """Download a mutual fund factsheet PDF, extract text, and add it to the factsheet RAG store."""
    try:
        url = (url or "").strip()
        if not url.startswith("http"):
            return "Invalid URL."
        data = download_pdf(url)
        doc_title = title.strip() or urlparse(url).path.split("/")[-1] or url
        chunks, pages, chars = extract_pdf_bytes(
            data, source_url=url, title=doc_title, max_pages=25
        )
        if not chunks:
            return f"Downloaded PDF but extracted no text: {url}"
        # Tag meta
        for c in chunks:
            c.meta["doc_type"] = "factsheet"
        store = get_factsheet_store()
        n = store.add_chunks(chunks)
        store.register_source(doc_title, url, pages, chars)
        return (
            f"Ingested factsheet '{doc_title}' from {url}\n"
            f"Pages used: {pages}, chars: {chars}, chunks: {n}\n"
            f"{store.summary()}"
        )
    except Exception as e:
        return f"Factsheet ingest failed for {url}: {e}"


@tool
def query_factsheet_rag(question: str, k: int = 6) -> str:
    """Retrieve relevant excerpts from ingested mutual fund factsheet PDFs (BM25 RAG)."""
    try:
        store = get_factsheet_store()
        hits = store.query(question, k=max(1, min(int(k or 6), 12)))
        if not hits:
            return (
                "No factsheets in the RAG store. "
                "Use search_fund_factsheet then ingest_fund_factsheet_pdf first."
            )
        blocks = [f"Factsheet RAG hits for: {question}", store.summary(), ""]
        for i, c in enumerate(hits, 1):
            blocks.append(
                f"--- Excerpt {i} | {c.title} | p.{c.page_start} ---\n"
                f"{c.text}\nSource: {c.source_url}"
            )
        return "\n\n".join(blocks)
    except Exception as e:
        return f"Factsheet RAG failed: {e}"


AMFI_TOOLS = [
    search_amfi_schemes,
    get_amfi_nav,
    list_amfi_categories,
    search_related_equity_funds,
    search_fund_factsheet,
    ingest_fund_factsheet_pdf,
    query_factsheet_rag,
]


def _theme_from_query(query: str, symbols: list[str]) -> list[str]:
    themes = []
    ql = (query or "").lower()
    if symbols:
        themes.append(" ".join(symbols))
    if any(x in ql for x in ("large", "bluechip", "nifty 50", "nifty50")):
        themes.append("large cap growth")
    if any(x in ql for x in ("flexi", "multi cap", "diversified")):
        themes.append("flexi cap growth")
    if any(x in ql for x in ("bank", "hdfc", "icici", "private bank")):
        themes.append("banking financial services equity")
    if any(x in ql for x in ("it ", "infosys", "tcs", "technology", "software")):
        themes.append("technology sector equity")
    if "index" in ql or "etf" in ql:
        themes.append("index fund growth")
    if "icici prudential" in ql or "pruinsight" in ql:
        themes.append("ICICI Prudential large cap growth")
    # Always include a generic equity desk theme
    themes.append("flexi cap direct growth")
    themes.append("large cap direct growth")
    # Unique preserve order
    out = []
    for t in themes:
        if t not in out:
            out.append(t)
    return out[:4]


def programmatic_mf_brief(
    query: str,
    symbols: list[str] | None = None,
    max_factsheets: int = 1,
) -> str:
    """Deterministic AMFI + optional factsheet pipeline for the MF agent."""
    symbols = symbols or []
    store = get_factsheet_store()
    store.clear()

    parts: list[str] = []
    parts.append(f"=== AMFI source ===\n{AMFI_NAV_URL}\n")

    # Category snapshot
    parts.append("=== Categories (sample filters) ===")
    for kw in ("Large Cap", "Flexi Cap", "Sectoral"):
        parts.append(list_amfi_categories.invoke({"keyword": kw}))

    # Related schemes for themes
    parts.append("\n=== Related schemes (AMFI NAV) ===")
    for theme in _theme_from_query(query, symbols):
        parts.append(f"\n# Theme: {theme}")
        parts.append(search_related_equity_funds.invoke({"theme": theme, "limit": 5}))

    # Explicit scheme search from query tokens
    parts.append("\n=== Direct scheme search ===")
    parts.append(search_amfi_schemes.invoke({"query": query, "limit": 6}))
    if symbols:
        for sym in symbols[:3]:
            parts.append(
                search_amfi_schemes.invoke(
                    {"query": f"{sym} index growth", "limit": 4}
                )
            )

    # Factsheet: pick a popular scheme name from first AMFI hits if possible
    factsheet_queries = []
    if "icici" in query.lower() or not query:
        factsheet_queries.append("ICICI Prudential Bluechip Fund factsheet")
    if symbols and any(s in ("HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN") for s in symbols):
        factsheet_queries.append("ICICI Prudential Banking and Financial Services Fund factsheet")
    factsheet_queries.append("HDFC Flexi Cap Fund factsheet PDF")
    factsheet_queries.append(f"{query} mutual fund factsheet PDF")

    ingest_logs = []
    ingested = 0
    parts.append("\n=== Factsheet search & ingest ===")
    for fq in factsheet_queries:
        if ingested >= max_factsheets:
            break
        search_out = search_fund_factsheet.invoke({"query": fq})
        parts.append(search_out)
        urls = re.findall(r"URL:\s*(\S+)", search_out)
        pdfs = [u for u in urls if ".pdf" in u.lower()] + [
            u for u in urls if ".pdf" not in u.lower()
        ]
        for url in pdfs[:3]:
            if ingested >= max_factsheets:
                break
            result = ingest_fund_factsheet_pdf.invoke({"url": url, "title": ""})
            ingest_logs.append(result)
            if result.startswith("Ingested"):
                ingested += 1
                break

    parts.append("\n".join(ingest_logs) if ingest_logs else "No factsheet ingested.")

    if ingested:
        parts.append("\n=== Factsheet RAG ===")
        for q in (
            "portfolio holdings top stocks sector allocation",
            "investment objective benchmark riskometer",
            "AUM expense ratio",
        ):
            parts.append(query_factsheet_rag.invoke({"question": q, "k": 4}))

    return "\n\n".join(parts)

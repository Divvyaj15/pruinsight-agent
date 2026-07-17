"""Macro research tools: FRED (global) + India market proxies + RBI policy context."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Optional

import requests
import yfinance as yf
from dotenv import load_dotenv
from langchain_core.tools import tool

from pruinsight.tools.search_providers import search_as_dicts

load_dotenv()

FRED_OBS_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_SERIES_URL = "https://api.stlouisfed.org/fred/series"

# Common FRED series useful for India equity / MF macro framing
FRED_PRESETS: dict[str, str] = {
    "FEDFUNDS": "US Federal Funds Effective Rate (%)",
    "DFF": "US Daily Fed Funds Rate (%)",
    "DGS10": "US 10-Year Treasury Yield (%)",
    "DGS2": "US 2-Year Treasury Yield (%)",
    "T10Y2Y": "US 10Y–2Y Yield Spread (pp)",
    "VIXCLS": "CBOE VIX",
    "DCOILWTICO": "WTI Crude Oil (USD/bbl)",
    "DEXINUS": "USD/INR (FRED, inverse convention note in output)",
    "DTWEXBGS": "Trade-Weighted US Dollar Index (Broad)",
    "CPIAUCSL": "US CPI All Urban Consumers",
    "UNRATE": "US Unemployment Rate (%)",
}

# Yahoo fallbacks when FRED key missing
YF_MACROS: dict[str, tuple[str, str]] = {
    "USDINR": ("INR=X", "USD/INR (Yahoo)"),
    "INDIAVIX": ("^INDIAVIX", "India VIX"),
    "NIFTY": ("^NSEI", "Nifty 50"),
    "SENSEX": ("^BSESN", "BSE Sensex"),
    "US10Y": ("^TNX", "US 10Y yield proxy (Yahoo ^TNX)"),
    "VIX": ("^VIX", "CBOE VIX (Yahoo)"),
    "WTI": ("CL=F", "WTI Crude futures (Yahoo)"),
    "GOLD": ("GC=F", "Gold futures (Yahoo)"),
}

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "PruInsightMacro/0.1 (educational)"})


def _fred_key() -> Optional[str]:
    return os.getenv("FRED_API_KEY") or os.getenv("FRED_KEY")


def _fmt(v: Any) -> str:
    try:
        return f"{float(v):,.4f}"
    except (TypeError, ValueError):
        return str(v)


def _yf_last(symbol: str, period: str = "3mo") -> dict[str, Any]:
    t = yf.Ticker(symbol)
    hist = t.history(period=period)
    if hist is None or hist.empty:
        info = t.info or {}
        price = info.get("regularMarketPrice") or info.get("previousClose")
        return {"last": price, "prev": None, "asof": None, "change_pct": None}
    close = hist["Close"].dropna()
    last = float(close.iloc[-1])
    prev = float(close.iloc[-2]) if len(close) > 1 else None
    chg = ((last / prev) - 1.0) * 100.0 if prev else None
    asof = close.index[-1]
    asof_s = asof.date().isoformat() if hasattr(asof, "date") else str(asof)
    # 1m / 3m returns if enough bars
    ret_1m = None
    ret_3m = None
    if len(close) >= 22:
        ret_1m = (last / float(close.iloc[-22]) - 1.0) * 100.0
    if len(close) >= 63:
        ret_3m = (last / float(close.iloc[-63]) - 1.0) * 100.0
    return {
        "last": last,
        "prev": prev,
        "asof": asof_s,
        "change_pct": chg,
        "ret_1m": ret_1m,
        "ret_3m": ret_3m,
    }


def _fred_observations(series_id: str, limit: int = 12) -> dict[str, Any]:
    key = _fred_key()
    if not key:
        raise ValueError(
            "FRED_API_KEY is not set. Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html "
            "or use get_india_market_macro / get_global_macro_snapshot (Yahoo fallbacks)."
        )
    series_id = series_id.strip().upper()
    # series meta
    meta_r = _SESSION.get(
        FRED_SERIES_URL,
        params={"series_id": series_id, "api_key": key, "file_type": "json"},
        timeout=30,
    )
    meta_r.raise_for_status()
    meta = (meta_r.json().get("seriess") or [{}])[0]
    title = meta.get("title") or FRED_PRESETS.get(series_id, series_id)
    units = meta.get("units") or ""

    end = datetime.utcnow().date()
    start = end - timedelta(days=400)
    obs_r = _SESSION.get(
        FRED_OBS_URL,
        params={
            "series_id": series_id,
            "api_key": key,
            "file_type": "json",
            "observation_start": start.isoformat(),
            "sort_order": "desc",
            "limit": max(limit, 5),
        },
        timeout=30,
    )
    obs_r.raise_for_status()
    obs = obs_r.json().get("observations") or []
    clean = []
    for o in obs:
        val = o.get("value")
        if val in (None, ".", ""):
            continue
        try:
            clean.append({"date": o.get("date"), "value": float(val)})
        except ValueError:
            continue
    return {"id": series_id, "title": title, "units": units, "observations": clean}


@tool
def get_fred_series(series_id: str, limit: int = 8) -> str:
    """Fetch a FRED macro time series (requires FRED_API_KEY in .env).

    Useful IDs: DGS10 (US 10Y), DFF (fed funds), VIXCLS, DCOILWTICO (WTI),
    DEXINUS (USDINR), T10Y2Y (curve spread), CPIAUCSL, UNRATE.
    Free key: https://fred.stlouisfed.org/docs/api/api_key.html
    """
    try:
        data = _fred_observations(series_id, limit=int(limit or 8))
        obs = data["observations"][: int(limit or 8)]
        if not obs:
            return f"No FRED observations for {series_id}."
        latest = obs[0]
        older = obs[min(5, len(obs) - 1)]
        delta = latest["value"] - older["value"] if older else None
        lines = [
            f"FRED series: {data['id']} — {data['title']}",
            f"Units: {data['units'] or 'N/A'}",
            f"Latest: {latest['value']} on {latest['date']}",
        ]
        if delta is not None:
            lines.append(f"Change vs ~prior point ({older['date']}): {delta:+.4f}")
        lines.append("Recent observations (newest first):")
        for o in obs:
            lines.append(f"  {o['date']}: {o['value']}")
        lines.append("Source: https://fred.stlouisfed.org/")
        return "\n".join(lines)
    except Exception as e:
        return f"FRED series failed ({series_id}): {e}"


@tool
def list_fred_presets() -> str:
    """List built-in FRED series IDs commonly used for equity/MF macro context."""
    lines = [
        "Preset FRED series (use with get_fred_series):",
        "Requires FRED_API_KEY in environment / .env",
        "",
    ]
    for sid, desc in FRED_PRESETS.items():
        lines.append(f"- {sid}: {desc}")
    lines.append("")
    lines.append("Free API key: https://fred.stlouisfed.org/docs/api/api_key.html")
    lines.append(f"Key currently set: {'yes' if _fred_key() else 'no (Yahoo fallbacks still work)'}")
    return "\n".join(lines)


@tool
def get_global_macro_snapshot() -> str:
    """Global macro dashboard for MF desk.

    Uses FRED when FRED_API_KEY is set; otherwise Yahoo Finance proxies
    (VIX, US10Y ^TNX, WTI, Gold, USD broad via USDINR).
    """
    lines = ["=== Global macro snapshot ===", ""]
    key = _fred_key()
    if key:
        lines.append("Primary source: FRED (St. Louis Fed)")
        for sid in ("DFF", "DGS10", "DGS2", "T10Y2Y", "VIXCLS", "DCOILWTICO", "DEXINUS"):
            try:
                data = _fred_observations(sid, limit=6)
                obs = data["observations"]
                if not obs:
                    lines.append(f"- {sid}: no data")
                    continue
                latest = obs[0]
                prev = obs[1] if len(obs) > 1 else None
                chg = ""
                if prev:
                    chg = f" (Δ {latest['value'] - prev['value']:+.4f} vs {prev['date']})"
                lines.append(
                    f"- {sid} | {data['title']}: {_fmt(latest['value'])} on {latest['date']}{chg}"
                )
            except Exception as e:
                lines.append(f"- {sid}: error — {e}")
    else:
        lines.append(
            "FRED_API_KEY not set — using Yahoo Finance proxies. "
            "Add free FRED key for official series."
        )
        for name, (sym, label) in YF_MACROS.items():
            if name in ("INDIAVIX", "NIFTY", "SENSEX", "USDINR"):
                continue  # india tool
            try:
                d = _yf_last(sym)
                chg = f", d/d {d['change_pct']:+.2f}%" if d.get("change_pct") is not None else ""
                lines.append(
                    f"- {label} ({sym}): {_fmt(d.get('last'))} as of {d.get('asof')}{chg}"
                )
            except Exception as e:
                lines.append(f"- {label}: error — {e}")

    lines.append("")
    lines.append("Sources: FRED API and/or Yahoo Finance via yfinance")
    return "\n".join(lines)


@tool
def get_india_market_macro() -> str:
    """India market macro proxies: Nifty, Sensex, India VIX, USD/INR (Yahoo/NSE data via yfinance).

    Complements RBI policy narrative (see get_rbi_policy_context). Not official RBI DBIE tables.
    """
    lines = [
        "=== India market macro proxies ===",
        "Source: Yahoo Finance tickers (NSE/BSE related) via yfinance",
        "",
    ]
    for key in ("NIFTY", "SENSEX", "INDIAVIX", "USDINR"):
        sym, label = YF_MACROS[key]
        try:
            d = _yf_last(sym)
            bits = [f"last={_fmt(d.get('last'))}", f"asof={d.get('asof')}"]
            if d.get("change_pct") is not None:
                bits.append(f"d/d={d['change_pct']:+.2f}%")
            if d.get("ret_1m") is not None:
                bits.append(f"~1m={d['ret_1m']:+.2f}%")
            if d.get("ret_3m") is not None:
                bits.append(f"~3m={d['ret_3m']:+.2f}%")
            lines.append(f"- {label} ({sym}): " + ", ".join(bits))
        except Exception as e:
            lines.append(f"- {label}: error — {e}")

    lines.append("")
    lines.append(
        "Note: For official RBI statistical tables (DBIE), see "
        "https://dbie.rbi.org.in/ — this tool uses liquid market proxies suitable for desk demos."
    )
    return "\n".join(lines)


@tool
def get_rbi_policy_context(query: str = "latest RBI MPC repo rate CRR inflation outlook India") -> str:
    """Search for latest RBI monetary policy / MPC / repo rate / inflation context.

    Multi-provider search (Tavily → Serper → DuckDuckGo), biased toward rbi.org.in.
    Official DBIE portal: https://dbie.rbi.org.in/
    Policy announcements: https://www.rbi.org.in/
    """
    try:
        q = (query or "").strip() or "latest RBI MPC repo rate CRR inflation outlook India"
        searches = [
            f"{q} site:rbi.org.in",
            f"{q} RBI monetary policy 2025 OR 2026",
        ]
        seen: set[str] = set()
        blocks: list[str] = [
            "=== RBI / India policy context (search) ===",
            "Primary portals: https://www.rbi.org.in/ | https://dbie.rbi.org.in/",
            "Search cascade: Tavily → Serper → DuckDuckGo",
            "",
        ]
        rank = 0
        providers: list[str] = []
        for sq in searches:
            items, provider, _errs = search_as_dicts(sq, max_results=5, mode="web")
            if provider:
                providers.append(provider)
            for r in items:
                url = (r.get("url") or "").strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                rank += 1
                title = r.get("title") or "Untitled"
                content = (r.get("content") or "")[:400]
                boost = " [RBI official]" if "rbi.org.in" in url.lower() else ""
                via = r.get("provider") or ""
                blocks.append(
                    f"{rank}. {title}{boost}\n   {content}\n   Source: {url}"
                    + (f"\n   via: {via}" if via else "")
                )
                if rank >= 8:
                    break
            if rank >= 8:
                break
        if rank == 0:
            return (
                "No RBI policy search results. "
                "Tried Tavily / Serper / DuckDuckGo — check network or keys."
            )
        if providers:
            blocks.insert(3, f"Providers used: {', '.join(dict.fromkeys(providers))}")
        blocks.append(
            "\nCaveat: Search snippets can lag or misstate rates — verify on rbi.org.in for IC work."
        )
        return "\n\n".join(blocks)
    except Exception as e:
        return f"RBI policy context search failed: {e}"


@tool
def get_macro_dashboard() -> str:
    """One-shot macro pack: India market proxies + RBI policy search + global snapshot.

    Best default tool for the macro agent.
    """
    parts = [
        get_india_market_macro.invoke({}),
        "",
        get_global_macro_snapshot.invoke({}),
        "",
        get_rbi_policy_context.invoke(
            {"query": "latest RBI MPC repo rate CRR SDF MSF inflation GDP outlook"}
        ),
    ]
    return "\n".join(parts)


MACRO_TOOLS = [
    get_fred_series,
    list_fred_presets,
    get_global_macro_snapshot,
    get_india_market_macro,
    get_rbi_policy_context,
    get_macro_dashboard,
]


def programmatic_macro_brief(query: str = "") -> str:
    """Deterministic macro pack for the macro agent (no LLM tool-choice required)."""
    parts = [
        f"User research query (for framing): {query}",
        "",
        get_macro_dashboard.invoke({}),
    ]
    if _fred_key():
        parts.append("")
        parts.append("=== Extra FRED detail (10Y, curve, oil) ===")
        for sid in ("DGS10", "T10Y2Y", "DCOILWTICO"):
            parts.append(get_fred_series.invoke({"series_id": sid, "limit": 5}))
            parts.append("")
    else:
        parts.append("")
        parts.append(
            "Note: FRED_API_KEY not configured. Global block used Yahoo proxies. "
            "Optional free key improves US rates / official series quality."
        )
    return "\n".join(parts)

"""Structured market data for Streamlit KPIs and charts (no LLM)."""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import yfinance as yf

from pruinsight.tools.deep_fundamentals import DEFAULT_PEERS


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:
            return None
        return f
    except (TypeError, ValueError):
        return None


def _pct_display(v: Any) -> Optional[float]:
    f = _safe_float(v)
    if f is None:
        return None
    # yfinance sometimes 0.138 for 13.8%
    if abs(f) <= 1.5:
        return f * 100.0
    return f


def fetch_symbol_snapshot(symbol: str) -> dict[str, Any]:
    """KPI-friendly snapshot for one NSE symbol."""
    sym = symbol.upper().replace(".NS", "").strip()
    t = yf.Ticker(f"{sym}.NS")
    info = t.info or {}
    price = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
    high = _safe_float(info.get("fiftyTwoWeekHigh"))
    low = _safe_float(info.get("fiftyTwoWeekLow"))
    vs_high = ((price / high) - 1.0) * 100.0 if price and high else None
    vs_low = ((price / low) - 1.0) * 100.0 if price and low else None
    return {
        "symbol": sym,
        "name": info.get("longName") or sym,
        "sector": info.get("sector") or "N/A",
        "industry": info.get("industry") or "N/A",
        "price": price,
        "prev_close": _safe_float(info.get("previousClose")),
        "market_cap": _safe_float(info.get("marketCap")),
        "pe": _safe_float(info.get("trailingPE")),
        "forward_pe": _safe_float(info.get("forwardPE")),
        "pb": _safe_float(info.get("priceToBook")),
        "roe": _pct_display(info.get("returnOnEquity")),
        "profit_margin": _pct_display(info.get("profitMargins")),
        "div_yield": _pct_display(info.get("dividendYield")),
        "beta": _safe_float(info.get("beta")),
        "high_52w": high,
        "low_52w": low,
        "vs_high_pct": vs_high,
        "vs_low_pct": vs_low,
        "target_mean": _safe_float(info.get("targetMeanPrice")),
    }


def fetch_price_history_df(symbol: str, period: str = "1y") -> pd.DataFrame:
    """Close price history for charts. Index = date, column = Close."""
    sym = symbol.upper().replace(".NS", "").strip()
    t = yf.Ticker(f"{sym}.NS")
    hist = t.history(period=period)
    if hist is None or hist.empty:
        return pd.DataFrame()
    out = hist[["Close"]].copy()
    out.index = pd.to_datetime(out.index).tz_localize(None)
    out.columns = [sym]
    return out


def fetch_peer_metrics_df(symbols: list[str]) -> pd.DataFrame:
    """Rows = symbols, columns = PE, PB, ROE, Beta for bar charts."""
    rows = []
    for s in symbols[:8]:
        snap = fetch_symbol_snapshot(s)
        rows.append(
            {
                "Symbol": snap["symbol"],
                "P/E": snap["pe"],
                "P/B": snap["pb"],
                "ROE %": snap["roe"],
                "Beta": snap["beta"],
                "Price": snap["price"],
            }
        )
    return pd.DataFrame(rows)


def resolve_peer_universe(symbols: list[str]) -> list[str]:
    """Primary symbols + default sector peers (deduped)."""
    out: list[str] = []
    for s in symbols:
        sym = s.upper().replace(".NS", "").strip()
        if sym and sym not in out:
            out.append(sym)
        for p in DEFAULT_PEERS.get(sym, []):
            if p not in out:
                out.append(p)
    return out[:8]


TAPE_TICKERS: list[tuple[str, str]] = [
    ("NIFTY 50", "^NSEI"),
    ("SENSEX", "^BSESN"),
    ("INDIA VIX", "^INDIAVIX"),
    ("USD/INR", "INR=X"),
]


def fetch_index_tape() -> list[dict[str, Any]]:
    """Compact index tape for the research-desk header (one batched download)."""
    empty = [{"label": lab, "last": None, "chg": None} for lab, _ in TAPE_TICKERS]
    tickers = [t for _, t in TAPE_TICKERS]
    try:
        data = yf.download(
            tickers,
            period="5d",
            interval="1d",
            group_by="ticker",
            auto_adjust=True,
            threads=True,
            progress=False,
        )
    except Exception:
        return empty

    if data is None or getattr(data, "empty", True):
        return empty

    out: list[dict[str, Any]] = []
    for label, ticker in TAPE_TICKERS:
        last = None
        prev = None
        try:
            if isinstance(data.columns, pd.MultiIndex):
                if ticker in data.columns.get_level_values(0):
                    closes = data[ticker]["Close"].dropna()
                else:
                    closes = pd.Series(dtype=float)
            else:
                closes = data["Close"].dropna()
            if len(closes) >= 1:
                last = _safe_float(closes.iloc[-1])
            if len(closes) >= 2:
                prev = _safe_float(closes.iloc[-2])
        except Exception:
            last = prev = None
        chg = ((last / prev) - 1.0) * 100.0 if last and prev else None
        out.append({"label": label, "last": last, "chg": chg})
    return out


def day_change_pct(snap: dict[str, Any]) -> Optional[float]:
    price = _safe_float(snap.get("price"))
    prev = _safe_float(snap.get("prev_close"))
    if price is None or prev is None or prev == 0:
        return None
    return ((price / prev) - 1.0) * 100.0


def format_inr_cr(val: Optional[float]) -> str:
    if val is None:
        return "N/A"
    # show in ₹ Cr for large caps
    if abs(val) >= 1e7:
        return f"₹{val / 1e7:,.0f} Cr"
    if abs(val) >= 1e5:
        return f"₹{val / 1e5:,.1f} L"
    return f"₹{val:,.2f}"


def format_num(val: Optional[float], suffix: str = "", decimals: int = 2) -> str:
    if val is None:
        return "N/A"
    return f"{val:,.{decimals}f}{suffix}"


def parse_report_sections(report: str) -> list[tuple[str, str]]:
    """Split markdown report into (heading, body) by ## headers."""
    if not report or not report.strip():
        return []
    lines = report.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current = "Overview"
    buf: list[str] = []
    for line in lines:
        if line.startswith("## "):
            if buf or sections:
                sections.append((current, buf))
            current = line[3:].strip()
            buf = []
        elif line.startswith("# ") and not sections and not any(buf):
            # title only
            current = line[2:].strip()
            buf = []
        else:
            buf.append(line)
    sections.append((current, buf))
    return [(h, "\n".join(b).strip()) for h, b in sections if h]

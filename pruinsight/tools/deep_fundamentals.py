"""Screener-style deep India fundamentals (yfinance-backed).

Step 5: richer ratios, quarterly statements, growth, holders — similar *shape*
to Screener.in snapshots, without scraping Screener (ToS / fragility).
"""

from __future__ import annotations

from typing import Any, Optional

import yfinance as yf
from langchain_core.tools import tool

from pruinsight.tools.market_tools import _fmt_num, _ns_ticker, _pct


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:  # NaN
            return None
        return f
    except (TypeError, ValueError):
        return None


def _df_table(df, title: str, max_rows: int = 12, max_cols: int = 4) -> str:
    if df is None or getattr(df, "empty", True):
        return f"{title}: N/A"
    cols = list(df.columns)[:max_cols]
    rows = list(df.index)[:max_rows]
    lines = [f"{title}:"]
    header = "Metric | " + " | ".join(
        str(c.date() if hasattr(c, "date") else c) for c in cols
    )
    lines.append(header)
    for row in rows:
        vals = []
        for c in cols:
            try:
                v = df.loc[row, c]
            except Exception:
                v = None
            f = _safe_float(v)
            if f is None:
                vals.append("N/A")
            else:
                # large numbers without decimals; ratios keep 2dp
                if abs(f) >= 1000:
                    vals.append(f"{f:,.0f}")
                else:
                    vals.append(f"{f:,.2f}")
        lines.append(f"{row} | " + " | ".join(vals))
    return "\n".join(lines)


def _row_lookup(df, names: list[str]) -> Optional[float]:
    """Find first matching row label (case-insensitive substring)."""
    if df is None or getattr(df, "empty", True):
        return None
    idx_map = {str(i).lower(): i for i in df.index}
    for want in names:
        w = want.lower()
        for key, orig in idx_map.items():
            if w == key or w in key:
                col = df.columns[0]
                return _safe_float(df.loc[orig, col])
    return None


def _growth(curr: Optional[float], prev: Optional[float]) -> str:
    if curr is None or prev is None or prev == 0:
        return "N/A"
    return f"{(curr / prev - 1.0) * 100.0:+.1f}%"


@tool
def get_quarterly_financials(symbol: str) -> str:
    """Quarterly income, balance sheet, and cash flow highlights for an NSE stock.

    Screener-style multi-period view. Bare symbol e.g. HDFCBANK (no .NS).
    """
    try:
        sym = symbol.upper().replace(".NS", "").strip()
        t = _ns_ticker(sym)
        parts = [
            f"Quarterly financials for {sym}.NS (yfinance):",
            _df_table(getattr(t, "quarterly_financials", None), "Quarterly income", 10, 4),
            "",
            _df_table(
                getattr(t, "quarterly_balance_sheet", None), "Quarterly balance sheet", 10, 4
            ),
            "",
            _df_table(getattr(t, "quarterly_cashflow", None), "Quarterly cash flow", 10, 4),
        ]
        return "\n".join(parts)
    except Exception as e:
        return f"Quarterly financials failed for {symbol}: {e}"


@tool
def get_key_ratios_growth(symbol: str) -> str:
    """Compute Screener-like key ratios and multi-year growth from annual statements + quote.

    Includes valuation, profitability, leverage, and simple revenue/EPS growth where data exists.
    """
    try:
        sym = symbol.upper().replace(".NS", "").strip()
        t = _ns_ticker(sym)
        info = t.info or {}
        fin = getattr(t, "financials", None)
        bs = getattr(t, "balance_sheet", None)
        cash = getattr(t, "cashflow", None)

        # Multi-period revenue / net income from annual income statement
        rev_growth = "N/A"
        ni_growth = "N/A"
        if fin is not None and not getattr(fin, "empty", True) and len(fin.columns) >= 2:
            rev0 = _row_lookup(fin.iloc[:, [0]], ["total revenue", "revenue", "operating revenue"])
            rev1 = _row_lookup(fin.iloc[:, [1]], ["total revenue", "revenue", "operating revenue"])
            # better: get by column
            def _metric_by_col(df, names, col_idx):
                if df is None or getattr(df, "empty", True) or col_idx >= len(df.columns):
                    return None
                sub = df[[df.columns[col_idx]]]
                return _row_lookup(sub, names)

            rev0 = _metric_by_col(fin, ["total revenue", "revenue"], 0)
            rev1 = _metric_by_col(fin, ["total revenue", "revenue"], 1)
            rev2 = _metric_by_col(fin, ["total revenue", "revenue"], 2) if len(fin.columns) > 2 else None
            ni0 = _metric_by_col(fin, ["net income", "net income common stockholders"], 0)
            ni1 = _metric_by_col(fin, ["net income", "net income common stockholders"], 1)
            rev_growth = f"YoY: {_growth(rev0, rev1)}"
            if rev2 is not None:
                rev_growth += f" | prior YoY: {_growth(rev1, rev2)}"
            ni_growth = f"YoY: {_growth(ni0, ni1)}"

        # Free cash flow simple
        fcf = None
        if cash is not None and not getattr(cash, "empty", True):
            ocf = _row_lookup(cash.iloc[:, [0]], ["operating cash flow", "total cash from operating activities"])
            capex = _row_lookup(
                cash.iloc[:, [0]],
                ["capital expenditure", "capital expenditures"],
            )
            if ocf is not None and capex is not None:
                # capex often negative in yfinance
                fcf = ocf + capex if capex < 0 else ocf - abs(capex)

        price = info.get("currentPrice") or info.get("regularMarketPrice")
        high52 = info.get("fiftyTwoWeekHigh")
        low52 = info.get("fiftyTwoWeekLow")
        pct_from_high = "N/A"
        pct_from_low = "N/A"
        pf, hf, lf = _safe_float(price), _safe_float(high52), _safe_float(low52)
        if pf and hf and hf != 0:
            pct_from_high = f"{(pf / hf - 1) * 100:+.1f}%"
        if pf and lf and lf != 0:
            pct_from_low = f"{(pf / lf - 1) * 100:+.1f}%"

        lines = [
            f"Key ratios & growth — {sym}.NS (Screener-style pack via yfinance)",
            "",
            "=== Valuation ===",
            f"Price: {_fmt_num(price, '₹')}",
            f"Market cap: {_fmt_num(info.get('marketCap'), '₹')}",
            f"Enterprise value: {_fmt_num(info.get('enterpriseValue'), '₹')}",
            f"P/E (TTM): {info.get('trailingPE', 'N/A')}",
            f"Forward P/E: {info.get('forwardPE', 'N/A')}",
            f"PEG: {info.get('pegRatio', 'N/A')}",
            f"P/B: {info.get('priceToBook', 'N/A')}",
            f"P/S (TTM): {info.get('priceToSalesTrailing12Months', 'N/A')}",
            f"EV/EBITDA: {info.get('enterpriseToEbitda', 'N/A')}",
            f"EV/Revenue: {info.get('enterpriseToRevenue', 'N/A')}",
            "",
            "=== Profitability / quality ===",
            f"ROE: {_pct(info.get('returnOnEquity'))}",
            f"ROA: {_pct(info.get('returnOnAssets'))}",
            f"Gross margin: {_pct(info.get('grossMargins'))}",
            f"Operating margin: {_pct(info.get('operatingMargins'))}",
            f"Profit margin: {_pct(info.get('profitMargins'))}",
            f"EBITDA margins: {_pct(info.get('ebitdaMargins'))}",
            "",
            "=== Leverage / liquidity ===",
            f"Debt/Equity: {info.get('debtToEquity', 'N/A')}",
            f"Current ratio: {info.get('currentRatio', 'N/A')}",
            f"Quick ratio: {info.get('quickRatio', 'N/A')}",
            f"Total cash: {_fmt_num(info.get('totalCash'), '₹')}",
            f"Total debt: {_fmt_num(info.get('totalDebt'), '₹')}",
            f"Book value/share: {_fmt_num(info.get('bookValue'), '₹')}",
            "",
            "=== Growth (annual, best-effort) ===",
            f"Revenue growth: {rev_growth}",
            f"Net income growth: {ni_growth}",
            f"Earnings growth (info): {_pct(info.get('earningsGrowth'))}",
            f"Revenue growth (info): {_pct(info.get('revenueGrowth'))}",
            f"Earnings quarterly growth: {_pct(info.get('earningsQuarterlyGrowth'))}",
            "",
            "=== Cash / dividends ===",
            f"Operating cashflow (info): {_fmt_num(info.get('operatingCashflow'), '₹')}",
            f"Free cashflow (info): {_fmt_num(info.get('freeCashflow'), '₹')}",
            f"FCF (computed from statements): {_fmt_num(fcf, '₹')}",
            f"Dividend yield: {_pct(info.get('dividendYield'))}",
            f"Payout ratio: {_pct(info.get('payoutRatio'))}",
            f"Trailing annual dividend rate: {info.get('trailingAnnualDividendRate', 'N/A')}",
            "",
            "=== Price range ===",
            f"52w high / low: {_fmt_num(high52, '₹')} / {_fmt_num(low52, '₹')}",
            f"vs 52w high: {pct_from_high} | vs 52w low: {pct_from_low}",
            f"Beta: {info.get('beta', 'N/A')}",
            f"Shares outstanding: {_fmt_num(info.get('sharesOutstanding'))}",
            f"Float shares: {_fmt_num(info.get('floatShares'))}",
            "",
            "Source: Yahoo Finance via yfinance (not Screener.in). Gaps are normal for some NSE names.",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Key ratios/growth failed for {symbol}: {e}"


@tool
def get_shareholding_overview(symbol: str) -> str:
    """Shareholding / holders overview for an NSE stock (best-effort via yfinance).

    Includes major holders, top institutional and mutual fund holders when Yahoo provides them.
    Promoter % may be missing for many Indian names on Yahoo — flag honestly.
    """
    try:
        sym = symbol.upper().replace(".NS", "").strip()
        t = _ns_ticker(sym)
        info = t.info or {}
        lines = [
            f"Shareholding overview — {sym}.NS",
            f"Held % insiders: {info.get('heldPercentInsiders', 'N/A')}",
            f"Held % institutions: {info.get('heldPercentInstitutions', 'N/A')}",
            "",
        ]

        def _append_df(label: str, df) -> None:
            lines.append(f"=== {label} ===")
            if df is None or getattr(df, "empty", True):
                lines.append("N/A")
            else:
                try:
                    lines.append(df.head(12).to_string())
                except Exception:
                    lines.append(str(df)[:2000])
            lines.append("")

        try:
            _append_df("Major holders", getattr(t, "major_holders", None))
        except Exception as e:
            lines.append(f"Major holders error: {e}\n")
        try:
            _append_df("Institutional holders", getattr(t, "institutional_holders", None))
        except Exception as e:
            lines.append(f"Institutional holders error: {e}\n")
        try:
            _append_df("Mutual fund holders", getattr(t, "mutualfund_holders", None))
        except Exception as e:
            lines.append(f"Mutual fund holders error: {e}\n")

        lines.append(
            "Note: For full Indian promoter/FII/DII break-up, use exchange filings / Screener / Capitaline. "
            "Yahoo coverage is incomplete for many NSE stocks."
        )
        return "\n".join(lines)
    except Exception as e:
        return f"Shareholding overview failed for {symbol}: {e}"


@tool
def get_earnings_calendar(symbol: str) -> str:
    """Upcoming/past earnings dates for an NSE stock (yfinance calendar, best-effort)."""
    try:
        sym = symbol.upper().replace(".NS", "").strip()
        t = _ns_ticker(sym)
        lines = [f"Earnings calendar — {sym}.NS", ""]
        try:
            ed = t.earnings_dates
            if ed is not None and not getattr(ed, "empty", True):
                lines.append(ed.head(10).to_string())
            else:
                lines.append("No earnings_dates table.")
        except Exception as e:
            lines.append(f"earnings_dates: {e}")
        try:
            cal = t.calendar
            if cal is not None:
                lines.append("")
                lines.append("Calendar object:")
                lines.append(str(cal)[:1500])
        except Exception:
            pass
        info = t.info or {}
        lines.append("")
        lines.append(f"earningsTimestamp (info): {info.get('earningsTimestamp', 'N/A')}")
        lines.append(f"exDividendDate: {info.get('exDividendDate', 'N/A')}")
        return "\n".join(lines)
    except Exception as e:
        return f"Earnings calendar failed for {symbol}: {e}"


@tool
def get_screener_style_snapshot(symbol: str) -> str:
    """One-shot Screener-style company snapshot for MF desk (NSE via yfinance).

    Combines quote/ratios, growth, quarterly highlights, and holders summary.
    Prefer this as the primary deep-fundamentals call per symbol.
    """
    try:
        sym = symbol.upper().replace(".NS", "").strip()
        parts = [
            get_key_ratios_growth.invoke({"symbol": sym}),
            "",
            get_quarterly_financials.invoke({"symbol": sym}),
            "",
            get_shareholding_overview.invoke({"symbol": sym}),
            "",
            get_earnings_calendar.invoke({"symbol": sym}),
        ]
        return "\n".join(parts)
    except Exception as e:
        return f"Screener-style snapshot failed for {symbol}: {e}"


# Sector default peers for common India large-caps (Screener-like peer set)
DEFAULT_PEERS: dict[str, list[str]] = {
    "HDFCBANK": ["ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN"],
    "ICICIBANK": ["HDFCBANK", "KOTAKBANK", "AXISBANK", "SBIN"],
    "KOTAKBANK": ["HDFCBANK", "ICICIBANK", "AXISBANK"],
    "AXISBANK": ["HDFCBANK", "ICICIBANK", "KOTAKBANK"],
    "SBIN": ["HDFCBANK", "ICICIBANK", "AXISBANK"],
    "TCS": ["INFY", "HCLTECH", "WIPRO", "TECHM"],
    "INFY": ["TCS", "HCLTECH", "WIPRO", "TECHM"],
    "HCLTECH": ["TCS", "INFY", "WIPRO"],
    "WIPRO": ["TCS", "INFY", "HCLTECH"],
    "RELIANCE": ["ONGC", "IOC", "BPCL"],
    "ITC": ["HINDUNILVR", "NESTLEIND", "BRITANNIA"],
    "HINDUNILVR": ["ITC", "NESTLEIND", "BRITANNIA"],
    "BHARTIARTL": ["IDEA", "RJIO"],  # RJIO may fail — peers best-effort
    "BAJFINANCE": ["BAJAJFINSV", "HDFC", "SBILIFE"],
    "MARUTI": ["M&M", "TATAMOTORS", "HEROMOTOCO"],
    "LT": ["SIE", "ABB"],
}


@tool
def get_default_peer_set(symbol: str) -> str:
    """Return a default peer list for common NSE large-caps and a peer metrics snapshot.

    If the symbol is unknown, returns guidance to pass peers manually to get_peer_snapshot.
    """
    try:
        from pruinsight.tools.market_tools import get_peer_snapshot

        sym = symbol.upper().replace(".NS", "").strip()
        peers = DEFAULT_PEERS.get(sym)
        if not peers:
            return (
                f"No default peer set for {sym}. "
                "Pass peers manually to get_peer_snapshot, e.g. 'TCS,INFY,HCLTECH'."
            )
        # filter self
        peers = [p for p in peers if p != sym][:5]
        combo = ",".join([sym] + peers)
        snap = get_peer_snapshot.invoke({"symbols": combo})
        return (
            f"Default peers for {sym}: {', '.join(peers)}\n"
            f"(Best-effort sector set; not exhaustive.)\n\n{snap}"
        )
    except Exception as e:
        return f"Default peer set failed for {symbol}: {e}"


DEEP_FUNDAMENTALS_TOOLS = [
    get_screener_style_snapshot,
    get_key_ratios_growth,
    get_quarterly_financials,
    get_shareholding_overview,
    get_earnings_calendar,
    get_default_peer_set,
]


def programmatic_deep_fundamentals(symbols: list[str]) -> str:
    """Deterministic deep pack for fundamentals agent (Screener-style)."""
    if not symbols:
        return "No symbols provided for deep fundamentals."
    blocks = []
    for sym in symbols[:4]:
        blocks.append(f"######## DEEP FUNDAMENTALS: {sym} ########")
        blocks.append(get_screener_style_snapshot.invoke({"symbol": sym}))
        blocks.append("")
        blocks.append(get_default_peer_set.invoke({"symbol": sym}))
        blocks.append("")
    return "\n".join(blocks)

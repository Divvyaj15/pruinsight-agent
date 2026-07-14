"""Research tools: web search, NSE market data, financials, news, macro indices."""

from __future__ import annotations

import os
from typing import Any, Optional

from dotenv import load_dotenv
from langchain_core.tools import tool
from tavily import TavilyClient
import yfinance as yf

load_dotenv()

_tavily: Optional[TavilyClient] = None

# Yahoo / yfinance index tickers useful for India MF research
INDEX_MAP = {
    "NIFTY": "^NSEI",
    "NIFTY50": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "NIFTYBANK": "^NSEBANK",
    "INDIAVIX": "^INDIAVIX",
    "VIX": "^INDIAVIX",
    "SENSEX": "^BSESN",
    "USDINR": "INR=X",
}


def _get_tavily() -> TavilyClient:
    global _tavily
    if _tavily is None:
        key = os.getenv("TAVILY_API_KEY")
        if not key:
            raise ValueError("TAVILY_API_KEY is not set in environment / .env")
        _tavily = TavilyClient(api_key=key)
    return _tavily


def _ns_ticker(symbol: str) -> yf.Ticker:
    sym = symbol.upper().replace(".NS", "").replace(".BO", "").strip()
    return yf.Ticker(f"{sym}.NS")


def _fmt_num(val: Any, prefix: str = "") -> str:
    if val is None:
        return "N/A"
    try:
        if isinstance(val, float):
            return f"{prefix}{val:,.2f}"
        if isinstance(val, int):
            return f"{prefix}{val:,}"
        return str(val)
    except (TypeError, ValueError):
        return str(val)


def _pct(val: Any) -> str:
    if val is None:
        return "N/A"
    try:
        # yfinance sometimes returns 0.15 for 15%, sometimes 15
        f = float(val)
        if abs(f) <= 1.5:
            f *= 100
        return f"{f:.2f}%"
    except (TypeError, ValueError):
        return str(val)


# ---------------------------------------------------------------------------
# Search / news
# ---------------------------------------------------------------------------


@tool
def web_search(query: str) -> str:
    """Search the web for latest financial news, analysis, filings mentions, and market outlook.

    Prefer India-focused queries (company name + NSE, RBI, sector + India).
    """
    try:
        results = _get_tavily().search(query, max_results=6, search_depth="advanced")
        items = results.get("results") or []
        if not items:
            return "No search results found."
        lines = []
        for i, r in enumerate(items, 1):
            title = r.get("title", "Untitled")
            content = r.get("content", "")
            url = r.get("url", "")
            score = r.get("score")
            score_s = f" (relevance {score:.2f})" if isinstance(score, (int, float)) else ""
            lines.append(f"{i}. {title}{score_s}\n   {content}\n   Source: {url}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"Search failed: {e}"


@tool
def news_search(query: str) -> str:
    """Search specifically for recent news articles about a company, sector, or macro topic.

    Uses Tavily topic=news when available; falls back to a news-biased web search.
    """
    try:
        client = _get_tavily()
        try:
            results = client.search(
                query, max_results=6, topic="news", days=14, search_depth="basic"
            )
        except TypeError:
            results = client.search(f"{query} latest news India", max_results=6)
        items = results.get("results") or []
        if not items:
            return "No recent news results found."
        lines = []
        for i, r in enumerate(items, 1):
            title = r.get("title", "Untitled")
            content = r.get("content", "")
            url = r.get("url", "")
            published = r.get("published_date") or r.get("publishedDate") or ""
            pub = f" | {published}" if published else ""
            lines.append(f"{i}. {title}{pub}\n   {content}\n   Source: {url}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"News search failed: {e}"


@tool
def get_company_news(symbol: str) -> str:
    """Fetch recent company news headlines from Yahoo Finance for an NSE stock.

    Use bare symbols like HDFCBANK, RELIANCE (no .NS).
    """
    try:
        sym = symbol.upper().replace(".NS", "").strip()
        ticker = _ns_ticker(sym)
        news = getattr(ticker, "news", None) or []
        if not news:
            return f"No Yahoo Finance news for {sym}.NS."
        lines = [f"Company news for {sym}.NS (Yahoo Finance):"]
        for i, item in enumerate(news[:8], 1):
            # yfinance news shape varies by version
            content = item.get("content") if isinstance(item.get("content"), dict) else None
            if content:
                title = content.get("title") or item.get("title") or "Untitled"
                pub = content.get("provider", {}).get("displayName", "")
                summary = content.get("summary") or content.get("description") or ""
                link = ""
                click = content.get("clickThroughUrl") or content.get("canonicalUrl") or {}
                if isinstance(click, dict):
                    link = click.get("url", "")
            else:
                title = item.get("title") or "Untitled"
                pub = item.get("publisher") or ""
                summary = item.get("summary") or ""
                link = item.get("link") or ""
            lines.append(
                f"{i}. {title}\n   Publisher: {pub or 'N/A'}\n   {summary[:400]}\n   {link}"
            )
        return "\n\n".join(lines)
    except Exception as e:
        return f"Company news failed for {symbol}: {e}"


# ---------------------------------------------------------------------------
# Fundamentals / prices
# ---------------------------------------------------------------------------


@tool
def get_stock_data(symbol: str) -> str:
    """Get current quote and key valuation metrics for an NSE-listed company.

    Use bare symbols like HDFCBANK, RELIANCE, TCS (without .NS suffix).
    """
    try:
        sym = symbol.upper().replace(".NS", "").strip()
        ticker = _ns_ticker(sym)
        info = ticker.info or {}
        if not info.get("longName") and not info.get("currentPrice"):
            fast = getattr(ticker, "fast_info", None)
            price = getattr(fast, "last_price", None) if fast else None
            if price is None:
                return f"No data found for {sym}.NS. Check the NSE symbol."
            return f"Symbol: {sym}.NS\nLast Price: ₹{price}"

        return f"""Company: {info.get('longName', 'N/A')}
Symbol: {sym}.NS
Sector: {info.get('sector', 'N/A')}
Industry: {info.get('industry', 'N/A')}
Business summary: {(info.get('longBusinessSummary') or 'N/A')[:500]}
Current Price: {_fmt_num(info.get('currentPrice'), '₹')}
Previous Close: {_fmt_num(info.get('previousClose'), '₹')}
Open: {_fmt_num(info.get('open'), '₹')}
Day Range: {_fmt_num(info.get('dayLow'), '₹')} – {_fmt_num(info.get('dayHigh'), '₹')}
52-Week High: {_fmt_num(info.get('fiftyTwoWeekHigh'), '₹')}
52-Week Low: {_fmt_num(info.get('fiftyTwoWeekLow'), '₹')}
Avg Volume: {_fmt_num(info.get('averageVolume'))}
P/E (TTM): {info.get('trailingPE', 'N/A')}
Forward P/E: {info.get('forwardPE', 'N/A')}
PEG Ratio: {info.get('pegRatio', 'N/A')}
Price/Book: {info.get('priceToBook', 'N/A')}
EV/EBITDA: {info.get('enterpriseToEbitda', 'N/A')}
ROE: {_pct(info.get('returnOnEquity'))}
ROA: {_pct(info.get('returnOnAssets'))}
Profit Margin: {_pct(info.get('profitMargins'))}
Operating Margin: {_pct(info.get('operatingMargins'))}
Debt/Equity: {info.get('debtToEquity', 'N/A')}
Current Ratio: {info.get('currentRatio', 'N/A')}
Market Cap: {_fmt_num(info.get('marketCap'), '₹')}
Enterprise Value: {_fmt_num(info.get('enterpriseValue'), '₹')}
Dividend Yield: {_pct(info.get('dividendYield'))}
Beta: {info.get('beta', 'N/A')}
Analyst Target (mean): {_fmt_num(info.get('targetMeanPrice'), '₹')}
Analyst Target (high/low): {_fmt_num(info.get('targetHighPrice'), '₹')} / {_fmt_num(info.get('targetLowPrice'), '₹')}
# Analyst opinions: {info.get('numberOfAnalystOpinions', 'N/A')}
"""
    except Exception as e:
        return f"Stock data failed for {symbol}: {e}"


@tool
def get_financials(symbol: str) -> str:
    """Get annual income-statement, balance-sheet, and cash-flow highlights for an NSE stock.

    Use bare symbols like HDFCBANK, RELIANCE (no .NS). Best-effort summary of latest periods.
    """
    try:
        sym = symbol.upper().replace(".NS", "").strip()
        ticker = _ns_ticker(sym)

        def _table_summary(df, title: str, max_rows: int = 8) -> str:
            if df is None or getattr(df, "empty", True):
                return f"{title}: N/A"
            # columns are periods; take up to 3 most recent
            cols = list(df.columns)[:3]
            rows = list(df.index)[:max_rows]
            lines = [f"{title} (latest periods):"]
            header = "Metric | " + " | ".join(str(c.date() if hasattr(c, "date") else c) for c in cols)
            lines.append(header)
            for row in rows:
                vals = []
                for c in cols:
                    v = df.loc[row, c] if row in df.index else None
                    try:
                        vals.append(f"{float(v):,.0f}" if v == v and v is not None else "N/A")
                    except (TypeError, ValueError):
                        vals.append(str(v))
                lines.append(f"{row} | " + " | ".join(vals))
            return "\n".join(lines)

        income = getattr(ticker, "financials", None)
        balance = getattr(ticker, "balance_sheet", None)
        cash = getattr(ticker, "cashflow", None)

        parts = [
            f"Financial statements for {sym}.NS (yfinance, annual):",
            _table_summary(income, "Income statement"),
            "",
            _table_summary(balance, "Balance sheet"),
            "",
            _table_summary(cash, "Cash flow"),
        ]
        return "\n".join(parts)
    except Exception as e:
        return f"Financials failed for {symbol}: {e}"


@tool
def get_price_history(symbol: str, period: str = "1y") -> str:
    """Get price performance stats for an NSE stock over a period.

    period: 1mo, 3mo, 6mo, 1y, 2y, 5y, ytd, max (default 1y).
    Returns start/end price, high/low, return %, and realized volatility estimate.
    """
    try:
        sym = symbol.upper().replace(".NS", "").strip()
        period = (period or "1y").lower().strip()
        allowed = {"1mo", "3mo", "6mo", "1y", "2y", "5y", "ytd", "max"}
        if period not in allowed:
            period = "1y"
        ticker = _ns_ticker(sym)
        hist = ticker.history(period=period)
        if hist is None or hist.empty:
            return f"No price history for {sym}.NS period={period}."
        close = hist["Close"].dropna()
        if close.empty:
            return f"No close prices for {sym}.NS."
        start_p = float(close.iloc[0])
        end_p = float(close.iloc[-1])
        high_p = float(close.max())
        low_p = float(close.min())
        ret = (end_p / start_p - 1.0) * 100.0
        # annualized vol from daily returns
        rets = close.pct_change().dropna()
        vol = float(rets.std() * (252 ** 0.5) * 100) if len(rets) > 5 else None
        return f"""Price history {sym}.NS (period={period}):
Start: ₹{start_p:,.2f} ({close.index[0].date() if hasattr(close.index[0], 'date') else close.index[0]})
End: ₹{end_p:,.2f} ({close.index[-1].date() if hasattr(close.index[-1], 'date') else close.index[-1]})
Period high/low (close): ₹{high_p:,.2f} / ₹{low_p:,.2f}
Total return: {ret:.2f}%
Ann. volatility (approx): {f'{vol:.2f}%' if vol is not None else 'N/A'}
Bars: {len(close)}
"""
    except Exception as e:
        return f"Price history failed for {symbol}: {e}"


@tool
def get_analyst_view(symbol: str) -> str:
    """Get analyst recommendation trend and price targets for an NSE stock (Yahoo data).

    Use bare symbols like HDFCBANK (no .NS). Data may be sparse for some Indian names.
    """
    try:
        sym = symbol.upper().replace(".NS", "").strip()
        ticker = _ns_ticker(sym)
        info = ticker.info or {}
        lines = [
            f"Analyst view for {sym}.NS:",
            f"Mean target: {_fmt_num(info.get('targetMeanPrice'), '₹')}",
            f"High / low target: {_fmt_num(info.get('targetHighPrice'), '₹')} / {_fmt_num(info.get('targetLowPrice'), '₹')}",
            f"Current: {_fmt_num(info.get('currentPrice'), '₹')}",
            f"# Analyst opinions: {info.get('numberOfAnalystOpinions', 'N/A')}",
            f"Recommendation key: {info.get('recommendationKey', 'N/A')}",
            f"Recommendation mean: {info.get('recommendationMean', 'N/A')}",
        ]
        try:
            rec = ticker.recommendations
            if rec is not None and not rec.empty:
                tail = rec.tail(6)
                lines.append("Recent recommendation rows:")
                lines.append(tail.to_string())
        except Exception:
            pass
        try:
            trend = getattr(ticker, "recommendations_summary", None)
            if trend is None:
                trend = getattr(ticker, "recommendations", None)
        except Exception:
            pass
        return "\n".join(lines)
    except Exception as e:
        return f"Analyst view failed for {symbol}: {e}"


# ---------------------------------------------------------------------------
# Macro / indices
# ---------------------------------------------------------------------------


@tool
def get_index_snapshot(name: str = "NIFTY") -> str:
    """Get a snapshot of a major India market index or USD/INR.

    Supported names: NIFTY, BANKNIFTY, INDIAVIX, SENSEX, USDINR.
    """
    try:
        key = (name or "NIFTY").upper().replace(" ", "").replace("^", "")
        yf_sym = INDEX_MAP.get(key)
        if not yf_sym:
            return (
                f"Unknown index '{name}'. Use one of: "
                + ", ".join(sorted(set(INDEX_MAP.keys())))
            )
        t = yf.Ticker(yf_sym)
        info = t.info or {}
        hist = t.history(period="5d")
        last = None
        prev = None
        if hist is not None and not hist.empty:
            last = float(hist["Close"].iloc[-1])
            if len(hist) > 1:
                prev = float(hist["Close"].iloc[-2])
        chg = ((last / prev - 1) * 100) if last and prev else None
        return f"""Index snapshot: {key} ({yf_sym})
Last: {_fmt_num(last if last is not None else info.get('regularMarketPrice'))}
Previous close: {_fmt_num(prev if prev is not None else info.get('previousClose'))}
Day change: {f'{chg:.2f}%' if chg is not None else 'N/A'}
52w high/low: {_fmt_num(info.get('fiftyTwoWeekHigh'))} / {_fmt_num(info.get('fiftyTwoWeekLow'))}
"""
    except Exception as e:
        return f"Index snapshot failed for {name}: {e}"


@tool
def get_peer_snapshot(symbols: str) -> str:
    """Compare quick metrics for multiple NSE peers.

    Pass a comma-separated list of bare symbols, e.g. 'HDFCBANK,ICICIBANK,KOTAKBANK'.
    """
    try:
        parts = [p.strip().upper().replace(".NS", "") for p in symbols.replace(";", ",").split(",")]
        parts = [p for p in parts if p][:8]
        if not parts:
            return "No symbols provided."
        lines = ["Peer snapshot (NSE):", "Symbol | Price | P/E | P/B | ROE | Mkt Cap | Beta"]
        for sym in parts:
            info = _ns_ticker(sym).info or {}
            lines.append(
                " | ".join(
                    [
                        sym,
                        _fmt_num(info.get("currentPrice"), "₹"),
                        str(info.get("trailingPE", "N/A")),
                        str(info.get("priceToBook", "N/A")),
                        _pct(info.get("returnOnEquity")),
                        _fmt_num(info.get("marketCap"), "₹"),
                        str(info.get("beta", "N/A")),
                    ]
                )
            )
        return "\n".join(lines)
    except Exception as e:
        return f"Peer snapshot failed: {e}"


# Registry for agent tool dispatch
ALL_TOOLS = [
    web_search,
    news_search,
    get_company_news,
    get_stock_data,
    get_financials,
    get_price_history,
    get_analyst_view,
    get_index_snapshot,
    get_peer_snapshot,
]

TOOL_BY_NAME = {t.name: t for t in ALL_TOOLS}


def invoke_tool_by_name(name: str, args: dict) -> str:
    """Dispatch a LangChain tool call by name."""
    tool_fn = TOOL_BY_NAME.get(name)
    if not tool_fn:
        return f"Unknown tool: {name}. Available: {', '.join(TOOL_BY_NAME)}"
    try:
        return str(tool_fn.invoke(args or {}))
    except Exception as e:
        return f"Tool {name} error: {e}"

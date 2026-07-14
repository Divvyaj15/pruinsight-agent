"""Fundamentals Analyst — valuation, statements, performance, peers, analyst view."""

from pruinsight.agents.tool_loop import run_with_tools
from pruinsight.state import AgentState
from pruinsight.tools.market_tools import (
    get_analyst_view,
    get_financials,
    get_peer_snapshot,
    get_price_history,
    get_stock_data,
)

SYSTEM = """You are a Fundamentals Analyst at ICICI Prudential AMC (PruInsight desk).

Your job:
1. Use tools for NSE data (bare symbols: HDFCBANK, RELIANCE, TCS — no .NS).
2. Typical tool use:
   - get_stock_data: quote + valuation + quality metrics
   - get_financials: annual income / balance sheet / cash flow highlights
   - get_price_history: performance & volatility over 1y (or 6mo/3mo)
   - get_analyst_view: Street targets / recommendation summary (may be sparse)
   - get_peer_snapshot: comma-separated peers for relative valuation
3. Cross-check against the market research context provided.
4. Be quantitative; flag missing data honestly.
5. Do NOT give buy/sell recommendations — portfolio-construction context only.

Output sections:
- Snapshot metrics
- Performance (price history)
- Financial statement highlights
- Valuation view (cheap / fair / rich — with caveats)
- Quality of business (returns, margins, balance sheet)
- Peer / analyst context (if available)
- What matters most for a mutual fund holding horizon
"""

FUNDAMENTALS_TOOLS = [
    get_stock_data,
    get_financials,
    get_price_history,
    get_analyst_view,
    get_peer_snapshot,
]


def _infer_symbols(state: AgentState) -> list[str]:
    if state.get("symbols"):
        return [s.upper().replace(".NS", "") for s in state["symbols"]]
    q = state.get("query", "")
    found: list[str] = []
    aliases = {
        "hdfc bank": "HDFCBANK",
        "hdfc": "HDFCBANK",
        "reliance": "RELIANCE",
        "tcs": "TCS",
        "infosys": "INFY",
        "infy": "INFY",
        "sbi": "SBIN",
        "state bank": "SBIN",
        "itc": "ITC",
        "icici bank": "ICICIBANK",
        "icici": "ICICIBANK",
        "axis bank": "AXISBANK",
        "kotak": "KOTAKBANK",
        "bharti airtel": "BHARTIARTL",
        "airtel": "BHARTIARTL",
        "l&t": "LT",
        "larsen": "LT",
        "wipro": "WIPRO",
        "hcl": "HCLTECH",
        "hcltech": "HCLTECH",
        "bajaj finance": "BAJFINANCE",
        "maruti": "MARUTI",
        "titan": "TITAN",
    }
    ql = q.lower()
    for phrase, sym in aliases.items():
        if phrase in ql and sym not in found:
            found.append(sym)
    return found


def fundamentals_node(state: AgentState) -> dict:
    """Pull and interpret NSE fundamentals for symbols in scope."""
    symbols = _infer_symbols(state)
    research = state.get("market_research") or "(no prior market research)"
    filings = state.get("filings_context") or "(no filings context)"
    symbol_line = (
        f"Primary symbols: {', '.join(symbols)}. Fetch data for each."
        if symbols
        else "Infer NSE symbols from the query and fetch data for the main names."
    )
    peers_hint = ""
    if len(symbols) >= 2:
        peers_hint = f"\nAlso call get_peer_snapshot with: {','.join(symbols)}"

    user_msg = f"""Query: {state['query']}
{symbol_line}{peers_hint}

Prior market research:
{research}

Primary-source / filings brief (prefer numbers disclosed in filings when reconciling):
{filings}

Use tools (stock data, financials, price history, analyst view as needed) and produce your analysis brief.
"""

    content, trace = run_with_tools(
        SYSTEM, user_msg, FUNDAMENTALS_TOOLS, temperature=0.1, max_rounds=2
    )

    # Ensure we at least attempted direct data if model skipped tools but we know symbols
    if symbols and not any(
        getattr(m, "type", None) == "tool" or m.__class__.__name__ == "ToolMessage"
        for m in trace
    ):
        dumps = []
        for sym in symbols:
            dumps.append(get_stock_data.invoke({"symbol": sym}))
            dumps.append(get_price_history.invoke({"symbol": sym, "period": "1y"}))
        from langchain_core.messages import HumanMessage

        from pruinsight.llm import get_llm

        final = get_llm(temperature=0.1).invoke(
            [
                HumanMessage(
                    content=(
                        user_msg
                        + "\n\nRaw tool dumps:\n\n"
                        + "\n\n".join(str(d) for d in dumps)
                        + "\n\nWrite the fundamentals brief now."
                    )
                )
            ]
        )
        content = final.content if isinstance(final.content, str) else str(final.content)
        trace = list(trace) + [final]

    return {
        "fundamentals": content,
        "symbols": symbols,
        "messages": trace,
    }

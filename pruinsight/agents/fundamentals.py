"""Fundamentals Analyst — Screener-style deep India fundamentals + peers."""

from langchain_core.messages import HumanMessage, SystemMessage

from pruinsight.llm import get_llm
from pruinsight.state import AgentState
from pruinsight.tools.deep_fundamentals import programmatic_deep_fundamentals

SYSTEM = """You are a Fundamentals Analyst at ICICI Prudential AMC (PruInsight desk).

You receive a **Screener-style deep fundamentals pack** (ratios, growth, quarterly
statements, holders, peers) built from Yahoo Finance / yfinance for NSE symbols.

Your job:
1. Interpret the pack quantitatively — valuation, quality, growth, leverage, cash.
2. Reconcile with filings brief when numbers conflict (prefer filings for disclosed facts).
3. Flag missing data honestly (Yahoo often lacks full Indian promoter/FII tables).
4. Peer context: relative P/E, P/B, ROE — not a ranking recommendation.
5. Do NOT give buy/sell recommendations — portfolio-construction framing only.

Output sections:
- Company / sector snapshot
- Valuation (cheap / fair / rich with caveats)
- Growth trajectory (revenue, profits, quarterly color)
- Quality & balance sheet
- Shareholding notes (if any)
- Peer comparison
- What matters for a mutual fund holding horizon
- Data gaps
"""


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
        "asian paints": "ASIANPAINT",
        "ultratech": "ULTRACEMCO",
        "sun pharma": "SUNPHARMA",
    }
    ql = q.lower()
    for phrase, sym in aliases.items():
        if phrase in ql and sym not in found:
            found.append(sym)
    return found


def fundamentals_node(state: AgentState) -> dict:
    """Deep Screener-style pack + LLM interpretation."""
    symbols = _infer_symbols(state)
    research = state.get("market_research") or "(no prior market research)"
    filings = state.get("filings_context") or "(no filings context)"

    # Deterministic deep data (reliable vs pure tool-calling)
    if symbols:
        deep_pack = programmatic_deep_fundamentals(symbols)
    else:
        deep_pack = (
            "No NSE symbols in scope — skip deep screener pack. "
            "Pass -s SYMBOLS (e.g. HDFCBANK) or name a major company in the query."
        )

    user_msg = f"""Query: {state['query']}
Symbols: {', '.join(symbols) or 'N/A'}

Prior market research (context):
{research[:2000]}

Primary-source / filings brief (prefer for disclosed facts):
{filings[:2500]}

Earnings / management transcript brief (tone & guidance color):
{(state.get('transcripts_context') or 'N/A')[:2000]}

=== Screener-style deep fundamentals pack (yfinance) ===
{deep_pack[:28000]}

Write the fundamentals analysis brief for the MF desk now.
"""

    messages = [
        SystemMessage(content=SYSTEM),
        HumanMessage(content=user_msg),
    ]
    response = get_llm(temperature=0.1).invoke(messages)
    content = response.content if isinstance(response.content, str) else str(response.content)

    return {
        "fundamentals": content,
        "symbols": symbols,
        "messages": [response],
    }

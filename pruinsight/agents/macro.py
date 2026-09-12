"""Macro agent — RBI policy context, India market proxies, FRED/global rates."""

from pruinsight.llm import invoke_chat
from pruinsight.state import AgentState
from pruinsight.tools.macro_tools import programmatic_macro_brief

SYSTEM = """You are a Macro & Rates Analyst at ICICI Prudential AMC (PruInsight desk).

You receive:
- India market proxies (Nifty, Sensex, India VIX, USD/INR)
- RBI / MPC policy search snippets (repo, liquidity, inflation narrative)
- Global macro (FRED if configured, else Yahoo proxies for US yields, VIX, oil, etc.)

Your job:
1. Summarize the **macro regime** relevant to Indian equities / MF portfolios.
2. Separate **hard numbers** (levels, changes) from **narrative** (policy snippets).
3. Link macro to the user's equity query (rates → banks/NBFCs, oil → energy, USDINR → IT/exporters, risk-off → beta).
4. Flag uncertainty and data lags. No buy/sell recommendations.

Output sections:
- India market snapshot (levels / recent moves)
- RBI / domestic policy read-through
- Global rates, USD, commodities, risk appetite
- Implications for the stocks/sectors under review
- What to monitor next (calendar / data releases)
"""


def macro_node(state: AgentState) -> dict:
    """Build macro brief from FRED/Yahoo/RBI search pack."""
    query = state.get("query") or ""
    symbols = state.get("symbols") or []
    raw = programmatic_macro_brief(query=query)

    user_msg = f"""Research query: {query}
Symbols: {', '.join(symbols) or 'N/A'}

Short market research context:
{(state.get('market_research') or 'N/A')[:1200]}

=== Raw macro data pack ===
{raw[:6000]}

Write the macro & rates brief for the MF desk now.
"""

    response = invoke_chat(SYSTEM, user_msg, role="macro")
    content = response.content if isinstance(response.content, str) else str(response.content)
    return {
        "macro_context": content,
        "messages": [response],
    }

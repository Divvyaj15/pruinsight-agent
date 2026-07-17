"""Risk Assessor agent — downside, concentration, and process risks."""

from pruinsight.agents.tool_loop import run_with_tools
from pruinsight.state import AgentState
from pruinsight.tools.market_tools import get_index_snapshot, get_price_history

SYSTEM = """You are a Risk & Portfolio Risk Analyst at ICICI Prudential AMC (PruInsight desk).

Your job:
1. Identify material downside risks for a mutual fund holding context.
2. Cover business, financial, regulatory, valuation, liquidity, and macro risks.
3. Optionally use tools:
   - get_price_history: realized volatility / drawdown context for symbols
   - get_index_snapshot: INDIAVIX, NIFTY, BANKNIFTY for market risk regime
4. Note what would invalidate a constructive thesis (kill criteria).
5. Stay proportional — high-probability vs tail risks.
6. Never issue buy/sell ratings. Frame risk for portfolio managers and compliance.

Output sections:
- Top risks (ranked)
- Market / volatility context (if tools used)
- Thesis invalidation triggers
- Portfolio construction considerations (size, liquidity, sector overlap)
- Monitoring checklist
"""

RISK_TOOLS = [get_price_history, get_index_snapshot]


def risk_node(state: AgentState) -> dict:
    """Assess risks using prior research/fundamentals; optional vol/index tools."""
    symbols = state.get("symbols") or []
    user_msg = f"""Query: {state['query']}
Symbols: {', '.join(symbols) or 'N/A'}

=== Market research ===
{state.get('market_research') or 'N/A'}

=== Filings / primary sources ===
{state.get('filings_context') or 'N/A'}

=== Earnings transcripts / management commentary ===
{state.get('transcripts_context') or 'N/A'}

=== Fundamentals ===
{state.get('fundamentals') or 'N/A'}

=== Mutual fund / AMFI context ===
{state.get('mf_context') or 'N/A'}

=== Macro / RBI / global rates ===
{state.get('macro_context') or 'N/A'}

If symbols are present, you may call get_price_history (period 1y) and get_index_snapshot (INDIAVIX and NIFTY).
Weight risks disclosed in filings highly. Use MF context for concentration / category / mandate risks.
Use macro for rates, USDINR, oil, and risk-regime sensitivity.
Produce a risk assessment brief for MF portfolio managers.
"""

    content, trace = run_with_tools(
        SYSTEM, user_msg, RISK_TOOLS, temperature=0.15, max_rounds=2
    )
    return {
        "risk_assessment": content,
        "messages": trace,
    }

"""MF Context agent — AMFI NAVs + fund factsheets for mutual-fund desk lens."""

from pruinsight.llm import invoke_chat
from pruinsight.state import AgentState
from pruinsight.tools.amfi_tools import programmatic_mf_brief

SYSTEM = """You are a Mutual Fund Products & Portfolio Context Analyst at ICICI Prudential AMC (PruInsight desk).

You receive AMFI official NAV universe extracts and (when available) mutual fund factsheet PDF excerpts.

Your job:
1. Frame how the research query / stocks sit in a **mutual fund** context (categories, representative schemes, NAV snapshot).
2. Prefer **AMFI** figures for NAV/date; prefer **factsheet** text for objective, benchmark, riskometer, top holdings (if present).
3. Call out ICICI Prudential schemes when they appear, but also show peer AMC examples for context — no product push.
4. Never give buy/sell recommendations on funds or stocks.
5. Be explicit when factsheets failed to ingest.

Output sections:
- Relevant AMFI categories & representative schemes (with NAV + date)
- Factsheet-backed notes (objective, benchmark, allocation/holdings if available)
- Implications for a fund manager researching the named stocks/sectors
- Gaps / data limitations
"""


def mf_context_node(state: AgentState) -> dict:
    """Pull AMFI + factsheet context and write mf_context brief."""
    query = state.get("query") or ""
    symbols = state.get("symbols") or []

    raw = programmatic_mf_brief(query=query, symbols=symbols, max_factsheets=1)

    user_msg = f"""Research query: {query}
Symbols under review: {', '.join(symbols) or 'N/A'}

Prior market research (short context):
{(state.get('market_research') or 'N/A')[:1500]}

Prior fundamentals (short context):
{(state.get('fundamentals') or 'N/A')[:1500]}

=== Raw AMFI + factsheet pipeline output ===
{raw[:6000]}

Write the mutual-fund desk context brief now.
"""

    response = invoke_chat(SYSTEM, user_msg, role="mf_context")
    content = response.content if isinstance(response.content, str) else str(response.content)

    return {
        "mf_context": content,
        "messages": [response],
    }

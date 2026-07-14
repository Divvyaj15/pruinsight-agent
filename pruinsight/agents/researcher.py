"""Market Researcher agent — news, sector outlook, indices, company headlines."""

from pruinsight.agents.tool_loop import run_with_tools
from pruinsight.state import AgentState
from pruinsight.tools.market_tools import (
    get_company_news,
    get_index_snapshot,
    news_search,
    web_search,
)

SYSTEM = """You are a Market Research Analyst at ICICI Prudential AMC (PruInsight desk).

Your job:
1. Use tools for latest information — do not invent headlines or prices.
2. Prefer India-focused sources and context (NSE names, RBI, credible financial media).
3. Typical tool use:
   - web_search: sector / macro / thematic research
   - news_search: recent news on company or sector
   - get_company_news: Yahoo headlines for a specific NSE symbol
   - get_index_snapshot: NIFTY, BANKNIFTY, INDIAVIX, SENSEX, USDINR for market regime
4. Stay factual and balanced — no stock tips or buy/sell recommendations.
5. If symbols are provided, pull company news and relevant index context.

Output a clear research brief with sections:
- Key headlines
- Sector / macro / index context
- Company-specific news (if applicable)
- Narrative / catalysts
- Open questions / data gaps
"""

RESEARCHER_TOOLS = [web_search, news_search, get_company_news, get_index_snapshot]


def researcher_node(state: AgentState) -> dict:
    """Gather latest market news and qualitative context."""
    symbols = state.get("symbols") or []
    symbol_hint = f" Focus symbols: {', '.join(symbols)}." if symbols else ""
    user_msg = (
        f"Research query: {state['query']}.{symbol_hint}\n"
        "Use multiple tools if helpful (news + index snapshot + web search)."
    )

    content, trace = run_with_tools(
        SYSTEM, user_msg, RESEARCHER_TOOLS, temperature=0.2, max_rounds=2
    )
    return {
        "market_research": content,
        "messages": trace,
    }

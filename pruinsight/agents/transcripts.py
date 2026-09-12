"""Earnings transcripts agent — management tone & Q&A via search + RAG."""

from pruinsight.llm import invoke_chat
from pruinsight.state import AgentState
from pruinsight.tools.transcripts_tools import programmatic_transcripts_brief

SYSTEM = """You are an Earnings Call / Management Communications Analyst at ICICI Prudential AMC (PruInsight desk).

You receive search hits and (when available) retrieved excerpts from earnings call / conference call transcripts.

Your job:
1. Extract **management guidance**, demand commentary, margin/NII/asset-quality color, capital allocation.
2. Capture **Q&A risks** and what analysts pressed on.
3. Separate **direct quotes / transcript-backed points** from gaps (no transcript ingested, paywall, short text).
4. Cross-check tone vs prior market research and filings when provided.
5. No buy/sell recommendations.

Output sections:
- Sources used (or why none)
- Key management messages / guidance
- Financial / operational color (segment, margins, growth drivers)
- Risks & Q&A themes
- Implications for a mutual fund holding horizon
- Gaps / confidence
"""


def transcripts_node(state: AgentState) -> dict:
    query = state.get("query") or ""
    symbols = state.get("symbols") or []
    raw = programmatic_transcripts_brief(query=query, symbols=symbols, max_docs=2)

    user_msg = f"""Research query: {query}
Symbols: {', '.join(symbols) or 'N/A'}

Prior market research (short):
{(state.get('market_research') or 'N/A')[:1200]}

Prior filings brief (short):
{(state.get('filings_context') or 'N/A')[:1200]}

=== Raw transcript pipeline output ===
{raw[:6000]}

Write the earnings transcript / management commentary brief now.
"""

    response = invoke_chat(SYSTEM, user_msg, role="transcripts")
    content = response.content if isinstance(response.content, str) else str(response.content)
    return {
        "transcripts_context": content,
        "messages": [response],
    }

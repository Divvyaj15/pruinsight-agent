"""Filings agent — SEBI/exchange/company PDF primary sources + RAG."""

from pruinsight.llm import invoke_chat
from pruinsight.state import AgentState
from pruinsight.tools.filings_tools import programmatic_filings_brief

SYSTEM = """You are a Primary-Source / Filings Analyst at ICICI Prudential AMC (PruInsight desk).

You receive:
1) Search hits for annual reports, quarterly results, investor decks, BSE/NSE/SEBI-linked docs
2) Ingest logs (which PDFs were loaded into RAG)
3) Retrieved excerpts from those PDFs

Your job:
- Distill what **management / official filings** actually say (facts, numbers, disclosed risks).
- Clearly separate **filing-backed statements** from gaps (missing PDFs, scanned-only docs, thin excerpts).
- Cite source titles/URLs when possible.
- No buy/sell recommendations.

Output sections:
- Sources used (or why none)
- Filing-backed highlights (financial / strategic)
- Disclosed risks & caveats from documents
- What is still unknown / not in the corpus
- Implications for a mutual fund holding horizon (neutral framing)
"""


def filings_node(state: AgentState) -> dict:
    """Search, ingest PDFs, RAG retrieve, then LLM brief on primary sources."""
    query = state.get("query") or ""
    symbols = state.get("symbols") or []
    market = state.get("market_research") or ""

    raw = programmatic_filings_brief(query=query, symbols=symbols, max_pdfs=2)

    user_msg = f"""Research query: {query}
Symbols: {', '.join(symbols) or 'N/A'}

Prior market research (context only — prefer filings when they conflict with headlines):
{market[:2500]}

=== Raw filing pipeline output ===
{raw[:6000]}

Write the primary-source / filings brief now.
"""

    response = invoke_chat(SYSTEM, user_msg, role="filings")
    content = response.content if isinstance(response.content, str) else str(response.content)

    return {
        "filings_context": content,
        "messages": [response],
    }

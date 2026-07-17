"""Shared LangGraph state for the PruInsight multi-agent workflow."""

from typing import Annotated, List, TypedDict
import operator

from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """State passed between agents in the research pipeline."""

    query: str
    symbols: List[str]

    market_research: str
    filings_context: str
    transcripts_context: str
    fundamentals: str
    mf_context: str
    macro_context: str
    risk_assessment: str

    final_report: str
    messages: Annotated[List[BaseMessage], operator.add]

"""Shared LangGraph state for the PruInsight multi-agent workflow."""

from typing import Annotated, List, TypedDict
import operator

from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """State passed between agents in the research pipeline.

    Each specialized agent reads prior findings and writes its own field.
    Messages accumulate tool/LLM traffic for debugging and future tool loops.
    """

    # User input
    query: str
    symbols: List[str]

    # Intermediate agent outputs
    market_research: str
    filings_context: str
    fundamentals: str
    mf_context: str
    risk_assessment: str

    # Final deliverable
    final_report: str

    # Optional chat history / tool traces
    messages: Annotated[List[BaseMessage], operator.add]

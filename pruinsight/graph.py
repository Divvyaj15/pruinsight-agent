"""LangGraph multi-agent workflow for PruInsight."""

from langgraph.graph import END, StateGraph

from pruinsight.agents.filings import filings_node
from pruinsight.agents.fundamentals import fundamentals_node
from pruinsight.agents.macro import macro_node
from pruinsight.agents.mf_context import mf_context_node
from pruinsight.agents.researcher import researcher_node
from pruinsight.agents.risk import risk_node
from pruinsight.agents.synthesizer import synthesizer_node
from pruinsight.agents.transcripts import transcripts_node
from pruinsight.state import AgentState


def build_graph():
    """Build and compile the PruInsight multi-agent graph.

    Pipeline:
        researcher → filings → transcripts → fundamentals → mf_context
        → macro → risk → synthesizer
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("researcher", researcher_node)
    workflow.add_node("filings", filings_node)
    workflow.add_node("transcripts", transcripts_node)
    workflow.add_node("fundamentals", fundamentals_node)
    workflow.add_node("mf_context", mf_context_node)
    workflow.add_node("macro", macro_node)
    workflow.add_node("risk", risk_node)
    workflow.add_node("synthesizer", synthesizer_node)

    workflow.set_entry_point("researcher")
    workflow.add_edge("researcher", "filings")
    workflow.add_edge("filings", "transcripts")
    workflow.add_edge("transcripts", "fundamentals")
    workflow.add_edge("fundamentals", "mf_context")
    workflow.add_edge("mf_context", "macro")
    workflow.add_edge("macro", "risk")
    workflow.add_edge("risk", "synthesizer")
    workflow.add_edge("synthesizer", END)

    return workflow.compile()


app = build_graph()

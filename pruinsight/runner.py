"""Shared entrypoint for CLI and Streamlit — run the multi-agent graph."""

from __future__ import annotations

from typing import Any

from pruinsight.graph import build_graph
from pruinsight.report_export import enrich_result_with_sources
from pruinsight.tracing import configure_tracing, run_config, tracing_status


def initial_state(query: str, symbols: list[str] | None = None) -> dict[str, Any]:
    return {
        "query": query.strip(),
        "symbols": [
            s.upper().replace(".NS", "").strip()
            for s in (symbols or [])
            if s.strip()
        ],
        "market_research": "",
        "filings_context": "",
        "transcripts_context": "",
        "fundamentals": "",
        "mf_context": "",
        "macro_context": "",
        "risk_assessment": "",
        "final_report": "",
        "messages": [],
    }


def run_research(
    query: str,
    symbols: list[str] | None = None,
    *,
    source: str = "cli",
) -> dict[str, Any]:
    """Invoke the full PruInsight pipeline; append Data sources section.

    When LangSmith is configured (LANGSMITH_API_KEY), each run is traced with
    tags/metadata for the 8-agent LangGraph pipeline.
    """
    # Must run before graph/LLM activity
    status = configure_tracing()

    graph = build_graph()
    config = run_config(query=query, symbols=symbols or [], source=source)
    result = graph.invoke(initial_state(query, symbols), config=config)
    out = enrich_result_with_sources(result)
    out["langsmith"] = status
    return out

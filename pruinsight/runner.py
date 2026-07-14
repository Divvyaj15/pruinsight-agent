"""Shared entrypoint for CLI and Streamlit — run the multi-agent graph."""

from __future__ import annotations

from typing import Any

from pruinsight.graph import build_graph
from pruinsight.report_export import enrich_result_with_sources


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
        "fundamentals": "",
        "mf_context": "",
        "risk_assessment": "",
        "final_report": "",
        "messages": [],
    }


def run_research(query: str, symbols: list[str] | None = None) -> dict[str, Any]:
    """Invoke the full PruInsight pipeline and return the full result state.

    Appends a **Data sources** section (providers + any PDFs ingested this run).
    """
    graph = build_graph()
    result = graph.invoke(initial_state(query, symbols))
    return enrich_result_with_sources(result)

"""Shared entrypoint for CLI and Streamlit — run the multi-agent graph."""

from __future__ import annotations

from typing import Any, Iterator

from pruinsight.graph import build_graph
from pruinsight.report_export import enrich_result_with_sources
from pruinsight.tracing import configure_tracing, run_config

PIPELINE_NODE_ORDER = [
    "researcher",
    "filings",
    "transcripts",
    "fundamentals",
    "mf_context",
    "macro",
    "risk",
    "synthesizer",
]


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


def stream_research(
    query: str,
    symbols: list[str] | None = None,
    *,
    source: str = "streamlit",
) -> Iterator[dict[str, Any]]:
    """Yield pipeline progress events, then a final enriched result.

    Events:
        {"event": "start", "node": None, "done": [], "active": first node, ...}
        {"event": "node_done", "node": <id>, "done": [...], "active": next|None, ...}
        {"event": "done", "node": None, "result": <enriched state>, ...}
    """
    status = configure_tracing()
    graph = build_graph()
    config = run_config(query=query, symbols=symbols or [], source=source)
    state: dict[str, Any] = initial_state(query, symbols)

    yield {
        "event": "start",
        "node": None,
        "done": [],
        "active": PIPELINE_NODE_ORDER[0],
        "state": state,
        "langsmith": status,
    }

    done: list[str] = []
    for update in graph.stream(state, config=config, stream_mode="updates"):
        if not isinstance(update, dict):
            continue
        for node, payload in update.items():
            if isinstance(payload, dict):
                state = {**state, **payload}
            if node not in done:
                done.append(node)
            nxt = None
            if node in PIPELINE_NODE_ORDER:
                idx = PIPELINE_NODE_ORDER.index(node)
                if idx + 1 < len(PIPELINE_NODE_ORDER):
                    nxt = PIPELINE_NODE_ORDER[idx + 1]
            yield {
                "event": "node_done",
                "node": node,
                "done": list(done),
                "active": nxt,
                "state": state,
                "langsmith": status,
            }

    out = enrich_result_with_sources(state)
    out["langsmith"] = status
    yield {
        "event": "done",
        "node": None,
        "done": list(done),
        "active": None,
        "result": out,
        "state": out,
        "langsmith": status,
    }

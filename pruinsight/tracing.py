"""LangSmith / LangChain tracing setup for PruInsight.

Enable by setting in `.env` (any of these work):

    LANGSMITH_API_KEY=lsv2_...
    LANGSMITH_TRACING=true
    LANGSMITH_PROJECT=pruinsight-agent

Legacy names also supported:

    LANGCHAIN_API_KEY=...
    LANGCHAIN_TRACING_V2=true
    LANGCHAIN_PROJECT=pruinsight-agent
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

_CONFIGURED = False
DEFAULT_PROJECT = "pruinsight-agent"


def _truthy(val: str | None) -> bool:
    if not val:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on"}


def tracing_status() -> dict[str, Any]:
    """Return current LangSmith config status (no secrets)."""
    load_dotenv()
    api_key = (
        os.getenv("LANGSMITH_API_KEY")
        or os.getenv("LANGCHAIN_API_KEY")
        or ""
    )
    project = (
        os.getenv("LANGSMITH_PROJECT")
        or os.getenv("LANGCHAIN_PROJECT")
        or DEFAULT_PROJECT
    )
    explicit_on = _truthy(os.getenv("LANGSMITH_TRACING")) or _truthy(
        os.getenv("LANGCHAIN_TRACING_V2")
    )
    # Auto-enable when key present unless explicitly disabled
    explicit_off = os.getenv("LANGSMITH_TRACING", "").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    } or os.getenv("LANGCHAIN_TRACING_V2", "").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }
    enabled = bool(api_key) and (explicit_on or (bool(api_key) and not explicit_off))
    # If key exists and neither on nor off set, we treat as ON (configure_tracing will set env)
    if api_key and not explicit_off and not explicit_on:
        enabled = True
    return {
        "enabled": enabled,
        "has_api_key": bool(api_key),
        "project": project,
        "endpoint": os.getenv("LANGSMITH_ENDPOINT")
        or os.getenv("LANGCHAIN_ENDPOINT")
        or "https://api.smith.langchain.com",
    }


def configure_tracing() -> dict[str, Any]:
    """Load env and enable LangSmith tracing for LangChain/LangGraph.

    Safe to call multiple times. Call as early as possible before LLM/graph use.
    """
    global _CONFIGURED
    load_dotenv()

    status = tracing_status()
    api_key = (
        os.getenv("LANGSMITH_API_KEY")
        or os.getenv("LANGCHAIN_API_KEY")
        or ""
    )
    project = status["project"]

    if not api_key:
        # Ensure tracing env is not left half-on without a key
        if _truthy(os.getenv("LANGSMITH_TRACING")) or _truthy(
            os.getenv("LANGCHAIN_TRACING_V2")
        ):
            # User asked for tracing but forgot key — leave flags; runs work without export
            pass
        _CONFIGURED = True
        return tracing_status()

    # Normalize both new and legacy env vars so all LangChain versions pick them up
    os.environ["LANGSMITH_API_KEY"] = api_key
    os.environ["LANGCHAIN_API_KEY"] = api_key
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGSMITH_PROJECT"] = project
    os.environ["LANGCHAIN_PROJECT"] = project

    endpoint = (
        os.getenv("LANGSMITH_ENDPOINT")
        or os.getenv("LANGCHAIN_ENDPOINT")
        or "https://api.smith.langchain.com"
    )
    os.environ["LANGSMITH_ENDPOINT"] = endpoint
    os.environ["LANGCHAIN_ENDPOINT"] = endpoint

    _CONFIGURED = True

    # Best-effort: verify client can be constructed (does not require network success)
    try:
        from langsmith import Client  # noqa: F401

        _ = Client(api_key=api_key, api_url=endpoint)
    except Exception:
        pass

    return tracing_status()


def run_config(
    *,
    query: str = "",
    symbols: list[str] | None = None,
    source: str = "cli",
) -> dict[str, Any]:
    """LangGraph invoke config: run name, tags, metadata for LangSmith UI."""
    symbols = symbols or []
    short_q = (query or "").strip().replace("\n", " ")
    if len(short_q) > 60:
        short_q = short_q[:57] + "..."
    run_name = f"pruinsight:{source}"
    if symbols:
        run_name += f":{','.join(symbols[:3])}"
    if short_q:
        run_name += f" — {short_q}"

    tags = [
        "pruinsight",
        "langgraph",
        f"source:{source}",
    ]
    for s in symbols[:5]:
        tags.append(f"symbol:{s}")

    return {
        "run_name": run_name[:200],
        "tags": tags,
        "metadata": {
            "app": "pruinsight-agent",
            "source": source,
            "query": (query or "")[:500],
            "symbols": symbols,
            "pipeline": (
                "researcher>filings>transcripts>fundamentals>"
                "mf_context>macro>risk>synthesizer"
            ),
        },
    }

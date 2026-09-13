"""Shared LLM client with multi-model / role routing (Groq by default).

Roles let you optimize cost/latency/quality:

    GROQ_MODEL_DEFAULT   — fallback for all roles
    GROQ_MODEL_FAST      — tool loops, short summaries (cheaper/faster)
    GROQ_MODEL_SMART     — synthesizer / final note (stronger writing)
    GROQ_MODEL_RESEARCH  — optional override for researcher tool loop
    GROQ_MODEL_ANALYSIS  — filings, fundamentals, risk, macro, mf, transcripts

Examples (.env):

    # Free Groq tier: stay on 20B (8k TPM). 120B needs Dev Tier.
    GROQ_MODEL_FAST=openai/gpt-oss-20b
    GROQ_MODEL_SMART=openai/gpt-oss-20b
    GROQ_MODEL_ANALYSIS=openai/gpt-oss-20b
    GROQ_MODEL_DEFAULT=openai/gpt-oss-20b
    GROQ_TPM_LIMIT=8000
"""

from __future__ import annotations

import os
import time
from functools import lru_cache
from typing import Any, Literal, Optional

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from pruinsight.tracing import configure_tracing

load_dotenv()
configure_tracing()

# Free / on_demand Groq often caps ~8000 TPM; a single oversized request also 413s.
# Default to 20B so one pipeline can finish without a paid Dev Tier.
DEFAULT_MODEL = os.getenv("GROQ_MODEL_DEFAULT", "openai/gpt-oss-20b")
DEFAULT_FAST = os.getenv("GROQ_MODEL_FAST", "openai/gpt-oss-20b")
DEFAULT_SMART = os.getenv("GROQ_MODEL_SMART", DEFAULT_MODEL)
DEFAULT_ANALYSIS = os.getenv("GROQ_MODEL_ANALYSIS", DEFAULT_MODEL)
MAX_COMPLETION_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "800"))
MAX_INPUT_CHARS = int(os.getenv("GROQ_MAX_INPUT_CHARS", "10000"))
TPM_LIMIT = int(os.getenv("GROQ_TPM_LIMIT", "8000"))

_last_llm_finish = 0.0

Role = Literal[
    "default",
    "fast",
    "smart",
    "research",
    "analysis",
    "synthesizer",
    "filings",
    "fundamentals",
    "mf_context",
    "macro",
    "risk",
    "transcripts",
    "tool_loop",
]

# Role → which model env bucket to use
_ROLE_BUCKET: dict[str, str] = {
    "default": "default",
    "fast": "fast",
    "smart": "smart",
    "synthesizer": "smart",
    "research": "research",
    "tool_loop": "fast",
    "analysis": "analysis",
    "filings": "analysis",
    "fundamentals": "analysis",
    "mf_context": "analysis",
    "macro": "analysis",
    "risk": "analysis",
    "transcripts": "analysis",
}

# Default temperatures by role (can still override in get_llm)
_ROLE_TEMP: dict[str, float] = {
    "tool_loop": 0.1,
    "research": 0.2,
    "filings": 0.15,
    "transcripts": 0.15,
    "fundamentals": 0.1,
    "mf_context": 0.15,
    "macro": 0.15,
    "risk": 0.15,
    "synthesizer": 0.2,
    "smart": 0.2,
    "fast": 0.1,
    "analysis": 0.15,
    "default": 0.1,
}


def resolve_model(role: str = "default", model: Optional[str] = None) -> str:
    """Pick model id for a role (explicit model= always wins)."""
    if model:
        return model
    bucket = _ROLE_BUCKET.get(role, "default")
    if bucket == "fast":
        return os.getenv("GROQ_MODEL_FAST") or DEFAULT_FAST
    if bucket == "smart":
        return os.getenv("GROQ_MODEL_SMART") or DEFAULT_SMART
    if bucket == "research":
        return (
            os.getenv("GROQ_MODEL_RESEARCH")
            or os.getenv("GROQ_MODEL_FAST")
            or DEFAULT_FAST
        )
    if bucket == "analysis":
        return os.getenv("GROQ_MODEL_ANALYSIS") or DEFAULT_ANALYSIS
    return os.getenv("GROQ_MODEL_DEFAULT") or DEFAULT_MODEL


def model_roster() -> dict[str, str]:
    """Resolved models for each logical role (for UI / debugging)."""
    roles = [
        "default",
        "fast",
        "smart",
        "research",
        "analysis",
        "tool_loop",
        "synthesizer",
    ]
    return {r: resolve_model(r) for r in roles}


def clip_text(text: Any, max_chars: int | None = None) -> str:
    """Hard-cap prompt text so a single Groq request stays under free-tier TPM."""
    s = "" if text is None else str(text)
    limit = MAX_INPUT_CHARS if max_chars is None else max_chars
    if limit <= 0 or len(s) <= limit:
        return s
    return s[: max(0, limit - 18)] + "\n...[truncated]..."


def _content_chars(content: Any) -> int:
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(_content_chars(b.get("text") if isinstance(b, dict) else b) for b in content)
    return len(str(content))


def estimate_tokens_from_chars(n_chars: int) -> int:
    return max(1, n_chars // 4)


def _is_tpm_or_size_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(
        s in msg
        for s in (
            "rate_limit",
            "request too large",
            "tokens per minute",
            "tpm",
            "413",
        )
    )


def _is_tool_choice_error(exc: BaseException) -> bool:
    """Groq gpt-oss often emits a tool call even when the request has no tools."""
    msg = str(exc)
    return "tool_use_failed" in msg or "Tool choice is none" in msg


_NO_TOOLS_RULE = (
    "\n\nHard rule: you have no tools in this step. Write markdown prose only. "
    "Do not emit function calls, JSON, or names like query_filings_rag / web_search."
)


def _pace_for_tokens(est_tokens: int) -> None:
    """Sleep so successive calls stay under GROQ_TPM_LIMIT (free = 8000/min)."""
    global _last_llm_finish
    tpm = max(TPM_LIMIT, 1)
    min_gap = (est_tokens / tpm) * 60.0 + 0.4
    wait = min_gap - (time.monotonic() - _last_llm_finish)
    if wait > 0:
        time.sleep(min(wait, 70.0))


def _mark_llm_finished() -> None:
    global _last_llm_finish
    _last_llm_finish = time.monotonic()


@lru_cache(maxsize=32)
def _cached_chatgroq(model: str, temperature: float, max_tokens: int) -> ChatGroq:
    """Cache clients per (model, temperature, max_tokens)."""
    return ChatGroq(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=os.getenv("GROQ_API_KEY"),
    )


def get_llm(
    temperature: Optional[float] = None,
    model: Optional[str] = None,
    *,
    role: Role | str = "default",
) -> ChatGroq:
    """Return a ChatGroq instance for a given agent role.

    Examples:
        get_llm(role="tool_loop")      # fast model, low temp
        get_llm(role="synthesizer")    # smart model
        get_llm(model="openai/gpt-oss-20b")  # explicit override
    """
    configure_tracing()
    temp = _ROLE_TEMP.get(role, 0.1) if temperature is None else temperature
    mid = resolve_model(role, model)
    return _cached_chatgroq(mid, round(float(temp), 3), MAX_COMPLETION_TOKENS)


def _fallback_brief(user: str) -> AIMessage:
    return AIMessage(
        content=(
            "Provider blocked a tool call on a no-tools step. Evidence already in context:\n\n"
            + clip_text(user, 4500)
        )
    )


def invoke_chat(
    system: str,
    user: str,
    *,
    role: Role | str = "default",
    temperature: Optional[float] = None,
) -> AIMessage:
    """Invoke with clipped prompts, TPM pacing, and shrink/retry on 413."""
    budget = MAX_INPUT_CHARS
    last_exc: BaseException | None = None
    sys = clip_text(system, 3200) + _NO_TOOLS_RULE
    tool_fails = 0
    work_user = user
    for _ in range(5):
        usr = clip_text(work_user, budget)
        messages = [SystemMessage(content=sys), HumanMessage(content=usr)]
        est = estimate_tokens_from_chars(_content_chars(sys) + _content_chars(usr)) + MAX_COMPLETION_TOKENS
        _pace_for_tokens(est)
        try:
            resp = get_llm(temperature=temperature, role=role).invoke(messages)
            _mark_llm_finished()
            return resp  # type: ignore[return-value]
        except Exception as extra:
            _mark_llm_finished()
            last_exc = extra
            if _is_tool_choice_error(extra):
                tool_fails += 1
                work_user = (
                    f"{user}\n\nWrite the brief in prose only from the evidence above. "
                    "Do not call tools."
                )
                if tool_fails >= 2:
                    return _fallback_brief(usr)
                continue
            if not _is_tpm_or_size_error(extra):
                raise
            budget = max(2400, budget // 2)
            time.sleep(12)
    assert last_exc is not None
    raise last_exc


def invoke_messages(
    messages: list,
    *,
    role: Role | str = "default",
    temperature: Optional[float] = None,
    bound_llm: Any | None = None,
) -> Any:
    """Paced invoke for tool-bound clients; retries TPM errors without shrinking tools."""
    chars = sum(_content_chars(getattr(m, "content", "")) for m in messages)
    est = estimate_tokens_from_chars(chars) + MAX_COMPLETION_TOKENS
    last_exc: BaseException | None = None
    client = bound_llm if bound_llm is not None else get_llm(temperature=temperature, role=role)
    for attempt in range(5):
        _pace_for_tokens(est)
        try:
            resp = client.invoke(messages)
            _mark_llm_finished()
            return resp
        except Exception as extra:
            _mark_llm_finished()
            last_exc = extra
            if _is_tool_choice_error(extra):
                raise
            if not _is_tpm_or_size_error(extra):
                raise
            time.sleep(12 + attempt * 8)
    assert last_exc is not None
    raise last_exc


def clear_llm_cache() -> None:
    """Drop cached clients (e.g. after changing API key in tests)."""
    _cached_chatgroq.cache_clear()

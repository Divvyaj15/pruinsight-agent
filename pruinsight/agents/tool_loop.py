"""Shared LLM + tool-calling loop for agents."""

from __future__ import annotations

from typing import Any, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from pruinsight.llm import clip_text, invoke_chat, invoke_messages, get_llm
from pruinsight.tools.market_tools import invoke_tool_by_name

_GROQ_TOOL_NONE = ("tool_use_failed", "Tool choice is none")
_MAX_TOOL_RESULT = 1600
_MAX_EVIDENCE = 6000


def _as_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        bits: list[str] = []
        for block in content:
            if isinstance(block, str):
                bits.append(block)
            elif isinstance(block, dict):
                if block.get("type") in ("text", "output_text"):
                    bits.append(str(block.get("text") or ""))
                elif "text" in block:
                    bits.append(str(block["text"]))
        return "\n".join(b for b in bits if b).strip()
    return str(content).strip()


def _tool_evidence(messages: Sequence[BaseMessage]) -> str:
    parts: list[str] = []
    for m in messages:
        if isinstance(m, ToolMessage):
            name = getattr(m, "name", None) or "tool"
            parts.append(f"[{name}]\n{m.content}")
        elif isinstance(m, AIMessage):
            text = _as_text(m.content)
            if text:
                parts.append(f"[model]\n{text}")
    return clip_text("\n\n".join(parts), _MAX_EVIDENCE)


def _is_groq_tool_choice_error(exc: BaseException) -> bool:
    msg = str(exc)
    return any(s in msg for s in _GROQ_TOOL_NONE)


def _synthesize_from_evidence(
    system: str,
    user: str,
    messages: Sequence[BaseMessage],
    temperature: float,
) -> AIMessage:
    evidence = _tool_evidence(messages)
    return invoke_chat(
        f"{system}\n\nWrite the brief from the evidence below. Do not request or emit tool calls.",
        f"{user}\n\nEvidence from tools:\n{evidence or '(no tool output)'}\n\n"
        "Produce the final structured brief now.",
        role="tool_loop",
        temperature=temperature,
    )


def run_with_tools(
    system: str,
    user: str,
    tools: Sequence[BaseTool],
    temperature: float = 0.15,
    max_rounds: int = 2,
) -> tuple[str, list[BaseMessage]]:
    """Run an LLM with tools for up to max_rounds of tool calls, then return final text.

    Returns (final_content, message_trace).
    """
    llm = get_llm(temperature=temperature, role="tool_loop")
    llm_tools = llm.bind_tools(list(tools))
    messages: list[BaseMessage] = [
        SystemMessage(content=clip_text(system, 2800)),
        HumanMessage(content=clip_text(user, 7000)),
    ]
    trace: list[BaseMessage] = []

    for _ in range(max_rounds):
        try:
            response = invoke_messages(
                messages, role="tool_loop", temperature=temperature, bound_llm=llm_tools
            )
        except Exception as exc:
            if _is_groq_tool_choice_error(exc):
                final = _synthesize_from_evidence(system, user, messages, temperature)
                trace.append(final)
                return _as_text(final.content), trace
            raise
        trace.append(response)
        messages.append(response)

        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            return _as_text(response.content), trace

        for tc in tool_calls:
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
            args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {}) or {}
            tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "tool")
            result = clip_text(str(invoke_tool_by_name(name, args)), _MAX_TOOL_RESULT)
            tm = ToolMessage(content=result, tool_call_id=tc_id, name=name or "tool")
            messages.append(tm)
            trace.append(tm)

    try:
        final = _synthesize_from_evidence(system, user, messages, temperature)
    except Exception as exc:
        if _is_groq_tool_choice_error(exc):
            evidence = _tool_evidence(messages)
            return evidence or "Tool loop finished without a brief.", trace
        raise

    trace.append(final)
    return _as_text(final.content), trace

"""Shared LLM + tool-calling loop for agents."""

from __future__ import annotations

from typing import Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from pruinsight.llm import get_llm
from pruinsight.tools.market_tools import invoke_tool_by_name


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
    llm = get_llm(temperature=temperature)
    llm_tools = llm.bind_tools(list(tools))
    messages: list[BaseMessage] = [
        SystemMessage(content=system),
        HumanMessage(content=user),
    ]
    trace: list[BaseMessage] = []

    for _ in range(max_rounds):
        response = llm_tools.invoke(messages)
        trace.append(response)
        messages.append(response)

        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            content = response.content if isinstance(response.content, str) else str(response.content)
            return content or "", trace

        for tc in tool_calls:
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
            args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {}) or {}
            tc_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "tool")
            result = invoke_tool_by_name(name, args)
            tm = ToolMessage(content=str(result), tool_call_id=tc_id)
            messages.append(tm)
            trace.append(tm)

    # Final synthesis without tools after tool rounds exhausted
    final = llm.invoke(
        messages
        + [
            HumanMessage(
                content=(
                    "You have tool results above. Produce your final structured brief now. "
                    "Do not call tools."
                )
            )
        ]
    )
    trace.append(final)
    content = final.content if isinstance(final.content, str) else str(final.content)
    return content or "", trace

"""Shared LLM client (Groq)."""

import os
from typing import Optional

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from pruinsight.tracing import configure_tracing

load_dotenv()
# Enable LangSmith before any ChatGroq / graph calls when key is present
configure_tracing()

DEFAULT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def get_llm(temperature: float = 0.1, model: Optional[str] = None) -> ChatGroq:
    """Return a configured ChatGroq instance (LangSmith-traced when enabled)."""
    configure_tracing()
    return ChatGroq(
        model=model or DEFAULT_MODEL,
        temperature=temperature,
        api_key=os.getenv("GROQ_API_KEY"),
    )

"""Shared LLM client (Groq)."""

import os
from typing import Optional

from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()

DEFAULT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"


def get_llm(temperature: float = 0.1, model: Optional[str] = None) -> ChatGroq:
    """Return a configured ChatGroq instance."""
    return ChatGroq(
        model=model or DEFAULT_MODEL,
        temperature=temperature,
        api_key=os.getenv("GROQ_API_KEY"),
    )

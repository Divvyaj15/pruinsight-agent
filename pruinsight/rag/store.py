"""In-process BM25 store for PDF filing chunks (no paid vector DB required)."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from typing import Optional

from rank_bm25 import BM25Okapi


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9%.\-]+", (text or "").lower())


@dataclass
class Chunk:
    chunk_id: str
    text: str
    source_url: str
    title: str
    page_start: int
    page_end: int
    meta: dict = field(default_factory=dict)


class FilingsStore:
    """Simple corpus of filing chunks with BM25 retrieval."""

    def __init__(self) -> None:
        self._chunks: list[Chunk] = []
        self._bm25: Optional[BM25Okapi] = None
        self._tokenized: list[list[str]] = []
        self._lock = threading.Lock()
        self.sources: list[dict] = []

    def clear(self) -> None:
        with self._lock:
            self._chunks.clear()
            self._bm25 = None
            self._tokenized = []
            self.sources = []

    def add_chunks(self, chunks: list[Chunk]) -> int:
        with self._lock:
            self._chunks.extend(chunks)
            self._rebuild()
            return len(chunks)

    def register_source(self, title: str, url: str, pages: int, chars: int) -> None:
        with self._lock:
            self.sources.append(
                {"title": title, "url": url, "pages": pages, "chars": chars}
            )

    def _rebuild(self) -> None:
        self._tokenized = [_tokenize(c.text) for c in self._chunks]
        self._bm25 = BM25Okapi(self._tokenized) if self._tokenized else None

    def query(self, question: str, k: int = 8) -> list[Chunk]:
        with self._lock:
            if not self._chunks or self._bm25 is None:
                return []
            tokens = _tokenize(question)
            if not tokens:
                return self._chunks[:k]
            scores = self._bm25.get_scores(tokens)
            ranked = sorted(
                range(len(scores)), key=lambda i: scores[i], reverse=True
            )
            out: list[Chunk] = []
            for i in ranked:
                if scores[i] <= 0 and out:
                    break
                out.append(self._chunks[i])
                if len(out) >= k:
                    break
            # If all scores zero, still return first k as fallback context
            return out or self._chunks[:k]

    def summary(self) -> str:
        with self._lock:
            if not self.sources:
                return "No filings ingested."
            lines = [f"Ingested sources ({len(self.sources)}):"]
            for i, s in enumerate(self.sources, 1):
                lines.append(
                    f"{i}. {s['title']} | pages={s['pages']} chars={s['chars']}\n   {s['url']}"
                )
            lines.append(f"Total chunks: {len(self._chunks)}")
            return "\n".join(lines)


_STORE: Optional[FilingsStore] = None
_FACTSHEET_STORE: Optional[FilingsStore] = None
_TRANSCRIPT_STORE: Optional[FilingsStore] = None
_STORE_LOCK = threading.Lock()


def get_filings_store() -> FilingsStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = FilingsStore()
        return _STORE


def get_factsheet_store() -> FilingsStore:
    """Separate BM25 corpus for mutual fund factsheet PDFs (step 2)."""
    global _FACTSHEET_STORE
    with _STORE_LOCK:
        if _FACTSHEET_STORE is None:
            _FACTSHEET_STORE = FilingsStore()
        return _FACTSHEET_STORE


def get_transcript_store() -> FilingsStore:
    """Separate BM25 corpus for earnings call transcripts (step 6)."""
    global _TRANSCRIPT_STORE
    with _STORE_LOCK:
        if _TRANSCRIPT_STORE is None:
            _TRANSCRIPT_STORE = FilingsStore()
        return _TRANSCRIPT_STORE

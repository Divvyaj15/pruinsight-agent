"""Report post-processing: data-sources appendix + Markdown / PDF export."""

from __future__ import annotations

import io
import os
import re
from datetime import datetime, timezone
from typing import Any


def build_sources_section(
    query: str = "",
    symbols: list[str] | None = None,
) -> str:
    """Markdown appendix describing where data was collected from."""
    symbols = symbols or []
    lines = [
        "## Data sources",
        "",
        "The following systems and providers were used to collect or generate material "
        "for this PruInsight note:",
        "",
        "### Platform / model",
        "1. **Groq API** — large language model inference for all agents "
        "(market research, filings, transcripts, fundamentals, MF context, macro, risk, synthesis).",
        "",
        "### Search & discovery",
        "2. **Web search cascade** — primary **Tavily**; if it fails or returns nothing, "
        "optional **Serper** (`SERPER_API_KEY`); then free **DuckDuckGo** (`ddgs`). "
        "Used for news, filings, **earnings transcripts**, fund factsheets, and RBI policy narrative.",
        "",
        "### Market data",
        "3. **Yahoo Finance** (via **yfinance**) — NSE quotes, annual/quarterly statements, "
        "key ratios & growth, holders (best-effort), history, company news, analyst targets, "
        "default peer sets (Screener-style pack), and market/macro proxies "
        "(**Nifty 50**, **Sensex**, **India VIX**, **USD/INR**, VIX, WTI, gold, US10Y).",
        "",
        "### Macro — global (optional official series)",
        "4. **FRED (Federal Reserve Bank of St. Louis)** — official US rates, curve, VIX, oil, USD/INR series "
        "when `FRED_API_KEY` is set (`https://fred.stlouisfed.org/`). If the key is absent, global block "
        "falls back to Yahoo proxies.",
        "",
        "### Macro — India policy",
        "5. **Reserve Bank of India** — policy/MPC context via multi-provider search of public RBI communications "
        "(`https://www.rbi.org.in/`). Official statistical warehouse: **DBIE** "
        "(`https://dbie.rbi.org.in/`) referenced for users; this demo does not scrape full DBIE tables.",
        "",
        "### Mutual fund industry data (AMFI)",
        "6. **AMFI** — scheme universe and latest NAVs from "
        "`https://portal.amfiindia.com/spages/NAVAll.txt`.",
        "",
        "### Primary documents (company filings)",
        "7. **Exchange / company PDF filings** — AR / results / IR docs via search + **pypdf** + **BM25** RAG "
        "(NSE / BSE / SEBI / company IR hosts).",
        "",
        "### Earnings transcripts",
        "8. **Earnings call / conference call transcripts** — discovered via multi-provider search, "
        "ingested as PDF or HTML text, chunked, and retrieved with a separate **BM25** transcript store "
        "(management guidance, Q&A themes). Many full transcripts are paywalled; coverage is best-effort.",
        "",
        "### Mutual fund documents (factsheets)",
        "9. **AMC fund factsheets** — PDF discovery + **pypdf** + separate **BM25** factsheet store.",
    ]

    try:
        from pruinsight.rag.store import (
            get_factsheet_store,
            get_filings_store,
            get_transcript_store,
        )

        sources = list(get_filings_store().sources)
        factsheets = list(get_factsheet_store().sources)
        transcripts = list(get_transcript_store().sources)
    except Exception:
        sources = []
        factsheets = []
        transcripts = []

    lines.append("")
    if sources:
        lines.append("### Company filings ingested in this run")
        for i, s in enumerate(sources, 1):
            title = s.get("title") or "Untitled PDF"
            url = s.get("url") or "N/A"
            pages = s.get("pages", "N/A")
            chars = s.get("chars", "N/A")
            lines.append(f"{i}. **{title}**")
            lines.append(f"   - Source URL: {url}")
            lines.append(f"   - Pages used: {pages} | Characters extracted: {chars}")
    else:
        lines.append("### Company filings ingested in this run")
        lines.append(
            "_No PDF filings were successfully ingested in this run. "
            "Any filings commentary may be based only on search snippets or secondary sources._"
        )

    lines.append("")
    if factsheets:
        lines.append("### Fund factsheets ingested in this run")
        for i, s in enumerate(factsheets, 1):
            title = s.get("title") or "Untitled PDF"
            url = s.get("url") or "N/A"
            pages = s.get("pages", "N/A")
            chars = s.get("chars", "N/A")
            lines.append(f"{i}. **{title}**")
            lines.append(f"   - Source URL: {url}")
            lines.append(f"   - Pages used: {pages} | Characters extracted: {chars}")
    else:
        lines.append("### Fund factsheets ingested in this run")
        lines.append(
            "_No fund factsheet PDFs were successfully ingested in this run. "
            "MF context may rely on AMFI NAV data and search snippets only._"
        )

    lines.append("")
    if transcripts:
        lines.append("### Earnings transcripts ingested in this run")
        for i, s in enumerate(transcripts, 1):
            title = s.get("title") or "Untitled transcript"
            url = s.get("url") or "N/A"
            pages = s.get("pages", "N/A")
            chars = s.get("chars", "N/A")
            lines.append(f"{i}. **{title}**")
            lines.append(f"   - Source URL: {url}")
            lines.append(f"   - Pages/sections: {pages} | Characters extracted: {chars}")
    else:
        lines.append("### Earnings transcripts ingested in this run")
        lines.append(
            "_No earnings transcripts were successfully ingested in this run. "
            "Management commentary may be limited to news/search snippets or missing entirely "
            "(paywalls, JS-only pages, or no public transcript found)._"
        )

    lines.extend(
        [
            "",
            "### Run metadata",
            f"- Query: {query or 'N/A'}",
            f"- Symbols: {', '.join(symbols) if symbols else 'N/A'}",
            f"- Generated (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S %Z')}",
            "",
            "### Source quality notes",
            "- Market data can be delayed, incomplete, or revised by providers.",
            "- PDF extraction uses a limited page range; scanned/image-only PDFs may yield little text.",
            "- Search results are not an exhaustive universe of all disclosures.",
            "- This is an educational multi-agent demo, not a licensed market-data terminal.",
        ]
    )
    return "\n".join(lines)


def append_sources_to_report(
    report: str,
    query: str = "",
    symbols: list[str] | None = None,
) -> str:
    """Append the data-sources section if not already present."""
    body = (report or "").rstrip()
    if re.search(r"^##\s+Data sources\b", body, flags=re.IGNORECASE | re.MULTILINE):
        return body + "\n"
    return body + "\n\n---\n\n" + build_sources_section(query, symbols) + "\n"


def enrich_result_with_sources(result: dict[str, Any]) -> dict[str, Any]:
    """Mutate/copy result so final_report includes data sources."""
    out = dict(result or {})
    report = out.get("final_report") or ""
    out["final_report"] = append_sources_to_report(
        report,
        query=out.get("query") or "",
        symbols=list(out.get("symbols") or []),
    )
    out["data_sources_md"] = build_sources_section(
        query=out.get("query") or "",
        symbols=list(out.get("symbols") or []),
    )
    return out


def _find_system_font() -> str | None:
    """Prefer a Unicode TTF so ₹ and en-dashes render in PDF."""
    candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _strip_md_for_pdf(text: str) -> list[tuple[str, str]]:
    """Convert markdown-ish lines to (style, plain_text) for PDF layout.

    style: h1 | h2 | h3 | body | bullet | hr
    """
    rows: list[tuple[str, str]] = []
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            rows.append(("body", ""))
            continue
        if re.match(r"^-{3,}$", line.strip()) or re.match(r"^\*{3,}$", line.strip()):
            rows.append(("hr", ""))
            continue
        if line.startswith("# "):
            rows.append(("h1", _inline_md_clean(line[2:])))
        elif line.startswith("## "):
            rows.append(("h2", _inline_md_clean(line[3:])))
        elif line.startswith("### "):
            rows.append(("h3", _inline_md_clean(line[4:])))
        elif re.match(r"^[-*]\s+", line.strip()):
            rows.append(("bullet", _inline_md_clean(re.sub(r"^[-*]\s+", "", line.strip()))))
        elif re.match(r"^\d+\.\s+", line.strip()):
            rows.append(("bullet", _inline_md_clean(line.strip())))
        else:
            rows.append(("body", _inline_md_clean(line)))
    return rows


def _inline_md_clean(text: str) -> str:
    t = text or ""
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"__(.+?)__", r"\1", t)
    t = re.sub(r"`([^`]+)`", r"\1", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", t)
    t = t.replace("**", "").replace("__", "")
    return t


def report_to_pdf_bytes(
    report: str,
    *,
    title: str = "PruInsight Research Note",
) -> bytes:
    """Render report text to PDF bytes (Unicode-friendly when system fonts exist)."""
    from fpdf import FPDF

    pdf = FPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(left=16, top=16, right=16)
    pdf.add_page()

    font_path = _find_system_font()
    if font_path:
        pdf.add_font("ReportFont", "", font_path)
        # Bold face if a bold sibling exists
        bold_guess = font_path.replace("arial.ttf", "arialbd.ttf").replace(
            "Arial.ttf", "Arial Bold.ttf"
        ).replace("calibri.ttf", "calibrib.ttf").replace("segoeui.ttf", "segoeuib.ttf")
        if os.path.isfile(bold_guess):
            pdf.add_font("ReportFont", "B", bold_guess)
            has_bold = True
        else:
            has_bold = False
        font_family = "ReportFont"
    else:
        font_family = "Helvetica"
        has_bold = True  # core fonts support B

    def set_font(style: str = "", size: int = 11) -> None:
        st = style if (style != "B" or has_bold) else ""
        pdf.set_font(font_family, st, size)

    def write_block(text: str, line_h: float = 5.5) -> None:
        """Write a paragraph at the left margin (fpdf2 multi_cell leaves x at right edge)."""
        pdf.set_x(pdf.l_margin)
        # w=0 uses full width between margins
        pdf.multi_cell(0, line_h, text if text is not None else " ")

    # Header band
    set_font("B", 16)
    write_block(title, 9)
    set_font("", 9)
    pdf.set_text_color(90, 90, 90)
    write_block(
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} · "
        "Educational demo only · Not investment advice",
        5,
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    usable = pdf.w - pdf.l_margin - pdf.r_margin

    for style, text in _strip_md_for_pdf(report):
        if style == "hr":
            y = pdf.get_y() + 2
            pdf.set_draw_color(180, 180, 180)
            pdf.line(pdf.l_margin, y, pdf.l_margin + usable, y)
            pdf.ln(6)
            continue
        if style == "h1":
            pdf.ln(2)
            set_font("B", 14)
            write_block(text or " ", 8)
            pdf.ln(1)
        elif style == "h2":
            pdf.ln(2)
            set_font("B", 12)
            write_block(text or " ", 7)
            pdf.ln(1)
        elif style == "h3":
            pdf.ln(1)
            set_font("B", 11)
            write_block(text or " ", 6)
        elif style == "bullet":
            set_font("", 10)
            write_block(f"• {text}" if text else " ", 5.5)
        else:
            set_font("", 10)
            if text == "":
                pdf.ln(3)
            else:
                write_block(text, 5.5)

    # Footer note on last content
    pdf.ln(6)
    set_font("", 8)
    pdf.set_text_color(100, 100, 100)
    write_block(
        "Data sources are listed in the final section of this report. "
        "PruInsight is not an official ICICI Prudential AMC product.",
        4,
    )

    out = pdf.output()
    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    # older API returned str
    return bytes(out)


def save_report_pdf(report: str, path: str, title: str = "PruInsight Research Note") -> str:
    data = report_to_pdf_bytes(report, title=title)
    with open(path, "wb") as f:
        f.write(data)
    return path

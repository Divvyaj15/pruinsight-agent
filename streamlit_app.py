"""
PruInsight Streamlit frontend — dashboard + multi-agent research note.

Run:
    .venv\\Scripts\\python.exe -m streamlit run streamlit_app.py
"""

from __future__ import annotations

import os
import re
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="PruInsight | Multi-Agent Research",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 1.25rem; max-width: 1200px; }
    .pru-badge {
        display: inline-block;
        padding: 0.2rem 0.65rem;
        border-radius: 999px;
        background: #e8f1ff;
        color: #1a4d8f;
        font-size: 0.8rem;
        font-weight: 600;
        margin-right: 0.35rem;
    }
    .pru-muted { color: #6b7280; font-size: 0.9rem; }
    .section-card {
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        background: #fafafa;
    }
    div[data-testid="stStatusWidget"] { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

PIPELINE_STEPS = [
    ("researcher", "Market Researcher", "Web/news search, company headlines, indices"),
    ("filings", "Filings Analyst", "SEBI/BSE/NSE/IR PDFs + BM25 RAG"),
    ("transcripts", "Transcripts Analyst", "Earnings call transcripts + BM25 RAG"),
    ("fundamentals", "Fundamentals Analyst", "Screener-style ratios, quarterly, holders, peers"),
    ("mf_context", "MF Context (AMFI)", "AMFI NAVs + fund factsheet RAG"),
    ("macro", "Macro Analyst", "RBI policy + India/global macro (FRED optional)"),
    ("risk", "Risk Assessor", "Downside risks + vol / VIX context"),
    ("synthesizer", "Report Synthesizer", "Final MF-desk note"),
]

TOOL_CATALOG = [
    ("web_search", "Tavily → Serper → DuckDuckGo cascade"),
    ("search_company_filings / transcripts", "Primary docs + earnings RAG"),
    ("get_screener_style_snapshot", "Deep ratios + quarterly + holders"),
    ("search_amfi_schemes", "AMFI official NAV universe"),
    ("get_macro_dashboard", "India + global macro pack"),
]

EXAMPLES = {
    "HDFC Bank (MF view)": {
        "query": "Latest insights on HDFC Bank for mutual fund perspective",
        "symbols": "HDFCBANK",
    },
    "Reliance large-cap": {
        "query": "Outlook on Reliance Industries for large-cap funds",
        "symbols": "RELIANCE",
    },
    "Private banks compare": {
        "query": "Compare private sector banks for diversified equity funds",
        "symbols": "HDFCBANK, ICICIBANK, KOTAKBANK",
    },
    "IT majors": {
        "query": "TCS vs Infosys — mutual fund holding considerations",
        "symbols": "TCS, INFY",
    },
}

AGENT_FIELDS = [
    ("market_research", "Market Research", "📰"),
    ("filings_context", "Filings", "📄"),
    ("transcripts_context", "Transcripts", "🎙️"),
    ("fundamentals", "Fundamentals", "📈"),
    ("mf_context", "MF / AMFI", "🏦"),
    ("macro_context", "Macro", "🌍"),
    ("risk_assessment", "Risk", "⚠️"),
]


def _parse_symbols(raw: str) -> list[str]:
    if not raw or not raw.strip():
        return []
    parts = [
        p.strip().upper().replace(".NS", "")
        for p in raw.replace(";", ",").split(",")
    ]
    return [p for p in parts if p]


def _keys_status() -> dict[str, bool]:
    try:
        from pruinsight.tools.search_providers import provider_status

        search = provider_status()
    except Exception:
        search = {
            "tavily": bool(os.getenv("TAVILY_API_KEY")),
            "serper": False,
            "duckduckgo": False,
        }
    return {
        "groq": bool(os.getenv("GROQ_API_KEY")),
        "tavily": search.get("tavily", False),
        "serper": search.get("serper", False),
        "duckduckgo": search.get("duckduckgo", False),
        "fred": bool(os.getenv("FRED_API_KEY") or os.getenv("FRED_KEY")),
    }


@st.cache_resource(show_spinner=False)
def _get_runner():
    from pruinsight.tracing import configure_tracing

    configure_tracing()
    from pruinsight.runner import run_research

    return run_research


@st.cache_data(ttl=300, show_spinner=False)
def _cached_snapshot(symbol: str) -> dict:
    from pruinsight.viz_data import fetch_symbol_snapshot

    return fetch_symbol_snapshot(symbol)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_history(symbol: str, period: str = "1y"):
    from pruinsight.viz_data import fetch_price_history_df

    return fetch_price_history_df(symbol, period)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_peers(symbols_tuple: tuple[str, ...]):
    from pruinsight.viz_data import fetch_peer_metrics_df, resolve_peer_universe

    universe = resolve_peer_universe(list(symbols_tuple))
    return fetch_peer_metrics_df(universe), universe


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### PruInsight")
        st.caption("Multi-agent equity research for a mutual-fund desk (demo).")

        keys = _keys_status()
        st.markdown("**API keys / search**")
        st.write(("✅" if keys["groq"] else "❌") + " `GROQ_API_KEY`")
        st.write(("✅" if keys["tavily"] else "⚪") + " `TAVILY_API_KEY`")
        st.write(("✅" if keys["serper"] else "⚪") + " `SERPER_API_KEY`")
        st.write(("✅" if keys["duckduckgo"] else "❌") + " DuckDuckGo (`ddgs`)")
        st.write(("✅" if keys["fred"] else "⚪") + " `FRED_API_KEY`")

        try:
            from pruinsight.tracing import configure_tracing, tracing_status

            configure_tracing()
            ls = tracing_status()
        except Exception:
            ls = {"enabled": False, "has_api_key": False, "project": "pruinsight-agent"}
        st.write(
            ("✅" if ls.get("enabled") else "⚪")
            + " LangSmith tracing"
            + (f" (`{ls.get('project')}`)" if ls.get("enabled") else " — set `LANGSMITH_API_KEY`")
        )
        if ls.get("enabled"):
            st.caption("Traces → https://smith.langchain.com")

        if not keys["groq"]:
            st.warning("Add `GROQ_API_KEY` to `.env` and restart.")
        else:
            st.caption("Search order: Tavily → Serper → DuckDuckGo")

        st.divider()
        st.markdown("**Pipeline**")
        for i, (_, name, desc) in enumerate(PIPELINE_STEPS, 1):
            st.caption(f"{i}. **{name}** — {desc}")

        with st.expander("Research tools"):
            for tool_name, tool_desc in TOOL_CATALOG:
                st.caption(f"`{tool_name}` — {tool_desc}")

        st.divider()
        st.markdown("**Examples**")
        choice = st.selectbox("Load example", ["—"] + list(EXAMPLES.keys()))
        if choice != "—" and st.button("Apply example", use_container_width=True):
            ex = EXAMPLES[choice]
            st.session_state["query_input"] = ex["query"]
            st.session_state["symbols_input"] = ex["symbols"]
            st.rerun()

        st.divider()
        st.caption("Not investment advice · Educational demo only")


def _render_kpi_dashboard(symbols: list[str]) -> None:
    if not symbols:
        st.info("Pass NSE symbols to show live KPI cards and charts.")
        return

    from pruinsight.viz_data import format_inr_cr, format_num

    st.subheader("Market snapshot")
    st.caption("Live data via yfinance (NSE) — independent of the LLM narrative.")

    for sym in symbols[:4]:
        try:
            snap = _cached_snapshot(sym)
        except Exception as e:
            st.warning(f"Could not load snapshot for {sym}: {e}")
            continue

        st.markdown(f"##### {snap['name']} (`{snap['symbol']}`)")
        st.caption(f"{snap['sector']} · {snap['industry']}")

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("Price", format_num(snap["price"], decimals=2) if snap["price"] else "N/A")
        c2.metric("P/E (TTM)", format_num(snap["pe"]))
        c3.metric("P/B", format_num(snap["pb"]))
        c4.metric("ROE", format_num(snap["roe"], "%", 1))
        c5.metric("Div yield", format_num(snap["div_yield"], "%", 2))
        c6.metric("Mkt cap", format_inr_cr(snap["market_cap"]))

        c7, c8, c9, c10 = st.columns(4)
        c7.metric("vs 52w high", format_num(snap["vs_high_pct"], "%", 1))
        c8.metric("vs 52w low", format_num(snap["vs_low_pct"], "%", 1))
        c9.metric("Beta", format_num(snap["beta"]))
        c10.metric(
            "Analyst tgt",
            format_num(snap["target_mean"], decimals=2) if snap["target_mean"] else "N/A",
        )


def _render_charts(symbols: list[str]) -> None:
    if not symbols:
        return

    st.subheader("Visualizations")
    left, right = st.columns(2)

    with left:
        st.markdown("**Price history (1Y)**")
        period = st.selectbox(
            "Period",
            ["6mo", "1y", "2y", "5y"],
            index=1,
            key="hist_period",
        )
        try:
            frames = []
            for sym in symbols[:3]:
                df = _cached_history(sym, period)
                if not df.empty:
                    frames.append(df)
            if frames:
                import pandas as pd

                chart_df = frames[0]
                for extra in frames[1:]:
                    chart_df = chart_df.join(extra, how="outer")
                st.line_chart(chart_df, height=320)
            else:
                st.caption("No price history available.")
        except Exception as e:
            st.caption(f"Price chart unavailable: {e}")

    with right:
        st.markdown("**Peer comparison**")
        try:
            peer_df, universe = _cached_peers(tuple(symbols))
            if peer_df.empty:
                st.caption("No peer metrics.")
            else:
                st.caption("Universe: " + ", ".join(universe))
                metric = st.selectbox(
                    "Metric",
                    ["P/E", "P/B", "ROE %", "Beta"],
                    key="peer_metric",
                )
                plot_df = peer_df.set_index("Symbol")[[metric]].dropna()
                if plot_df.empty:
                    st.caption(f"No data for {metric}.")
                else:
                    st.bar_chart(plot_df, height=320)
                with st.expander("Peer table"):
                    st.dataframe(peer_df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.caption(f"Peer chart unavailable: {e}")

    # 52w position as a simple gauge-like bar for primary symbol
    try:
        primary = symbols[0]
        snap = _cached_snapshot(primary)
        lo, hi, px = snap["low_52w"], snap["high_52w"], snap["price"]
        if lo and hi and px and hi > lo:
            st.markdown(f"**52-week range · {primary}**")
            pos = (px - lo) / (hi - lo)
            st.progress(min(max(pos, 0.0), 1.0))
            a, b, c = st.columns(3)
            a.caption(f"Low ₹{lo:,.2f}")
            b.caption(f"Now ₹{px:,.2f} ({pos*100:.0f}% of range)")
            c.caption(f"High ₹{hi:,.2f}")
    except Exception:
        pass


def _render_report_structured(report: str) -> None:
    from pruinsight.viz_data import parse_report_sections

    sections = parse_report_sections(report)
    if not sections:
        st.markdown(report)
        return

    # Highlight executive summary / first section if present
    exec_idx = next(
        (i for i, (h, _) in enumerate(sections) if "executive" in h.lower() or i == 0),
        0,
    )
    title_h, title_b = sections[0]
    if not title_h.lower().startswith("executive") and len(sections) > 1:
        st.markdown(f"### {title_h}")
        if title_b:
            st.markdown(title_b)

    # Section navigator
    labels = [h for h, _ in sections]
    tab_labels = []
    for h in labels:
        short = h if len(h) <= 28 else h[:25] + "…"
        tab_labels.append(short)

    tabs = st.tabs(tab_labels)
    for tab, (heading, body) in zip(tabs, sections):
        with tab:
            st.markdown(f"#### {heading}")
            if body:
                st.markdown(body)
            else:
                st.caption("_Empty section_")

    with st.expander("Full report (single page)", expanded=False):
        st.markdown(report)


def _render_agent_intermediates(result: dict, show_steps: bool) -> None:
    if not show_steps:
        return
    st.subheader("Agent workpapers")
    st.caption("Raw intermediate briefs from each specialized agent.")

    # Compact status row
    cols = st.columns(len(AGENT_FIELDS))
    for col, (key, label, icon) in zip(cols, AGENT_FIELDS):
        text = result.get(key) or ""
        ok = len(text.strip()) > 40
        col.metric(f"{icon} {label}", "Ready" if ok else "Thin/empty")

    tabs = st.tabs([f"{icon} {label}" for _, label, icon in AGENT_FIELDS] + ["Pipeline"])
    for i, (key, label, _) in enumerate(AGENT_FIELDS):
        with tabs[i]:
            content = result.get(key) or "_No output_"
            st.markdown(content)
    with tabs[-1]:
        for i, (_, name, desc) in enumerate(PIPELINE_STEPS, 1):
            st.markdown(f"{i}. **{name}** — {desc}")


def _render_downloads(report: str) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"pruinsight_note_{stamp}"

    pdf_bytes = None
    pdf_error = None
    try:
        from pruinsight.report_export import report_to_pdf_bytes

        pdf_bytes = report_to_pdf_bytes(report, title="PruInsight Research Note")
    except Exception as e:
        pdf_error = str(e)

    d1, d2, d3 = st.columns(3)
    with d1:
        st.download_button(
            "Download Markdown (.md)",
            data=report,
            file_name=f"{base}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with d2:
        if pdf_bytes:
            st.download_button(
                "Download PDF (.pdf)",
                data=pdf_bytes,
                file_name=f"{base}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            st.button("PDF unavailable", disabled=True, use_container_width=True)
            if pdf_error:
                st.caption(pdf_error)
    with d3:
        # Strip markdown-ish for a plain text export
        plain = re.sub(r"[#*_`]", "", report)
        st.download_button(
            "Download plain text (.txt)",
            data=plain,
            file_name=f"{base}.txt",
            mime="text/plain",
            use_container_width=True,
        )


def main() -> None:
    _render_sidebar()

    st.title("PruInsight Research Desk")
    st.markdown(
        '<span class="pru-badge">LangGraph</span>'
        '<span class="pru-badge">Groq</span>'
        '<span class="pru-badge">Tavily</span>'
        '<span class="pru-badge">yfinance</span>'
        '<span class="pru-badge">AMFI</span>',
        unsafe_allow_html=True,
    )
    st.write(
        "Multi-agent pipeline with **KPIs**, **charts**, and a **sectioned research note**."
    )

    if "query_input" not in st.session_state:
        st.session_state["query_input"] = EXAMPLES["HDFC Bank (MF view)"]["query"]
    if "symbols_input" not in st.session_state:
        st.session_state["symbols_input"] = EXAMPLES["HDFC Bank (MF view)"]["symbols"]

    with st.form("research_form", clear_on_submit=False):
        query = st.text_area(
            "Research query",
            key="query_input",
            height=90,
            placeholder="e.g. Latest insights on HDFC Bank for mutual fund perspective",
        )
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            symbols_raw = st.text_input(
                "NSE symbols (comma-separated)",
                key="symbols_input",
                placeholder="HDFCBANK, ICICIBANK",
                help="Bare tickers without .NS — enables KPIs & charts",
            )
        with col2:
            show_steps = st.checkbox("Show agent workpapers", value=True)
        with col3:
            show_viz = st.checkbox("Show charts & KPIs", value=True)

        submitted = st.form_submit_button(
            "Generate research note",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not query or not query.strip():
            st.error("Please enter a research query.")
            return

        keys = _keys_status()
        if not keys["groq"]:
            st.error("`GROQ_API_KEY` is missing from `.env`.")
            return
        if not keys["tavily"] and not keys["serper"] and not keys["duckduckgo"]:
            st.error("No search backend. Set Tavily/Serper or install `ddgs`.")
            return

        symbols = _parse_symbols(symbols_raw)
        run_research = _get_runner()

        progress = st.progress(0, text="Starting multi-agent pipeline…")
        status = st.empty()
        status.info(
            "Running: researcher → filings → transcripts → fundamentals → "
            "mf → macro → risk → synthesizer …"
        )
        progress.progress(15, text="Agents working (often 1–3 minutes)…")

        try:
            with st.spinner("Running multi-agent graph…"):
                result = run_research(query, symbols, source="streamlit")
        except Exception as e:
            progress.empty()
            status.empty()
            st.error(f"Pipeline failed: {e}")
            with st.expander("Error details"):
                st.exception(e)
            return

        progress.progress(100, text="Done")
        ls = result.get("langsmith") or {}
        if ls.get("enabled"):
            status.success(
                f"Research note ready · LangSmith project: `{ls.get('project')}` "
                "(open smith.langchain.com to inspect the graph)"
            )
        else:
            status.success("Research note ready.")

        st.session_state["last_result"] = result
        st.session_state["last_query"] = query
        st.session_state["last_symbols"] = symbols
        st.session_state["show_steps"] = show_steps
        st.session_state["show_viz"] = show_viz

    result = st.session_state.get("last_result")
    if not result:
        st.info(
            "Enter a query (and ideally NSE symbols), then click "
            "**Generate research note**. Charts use live market data."
        )
        return

    query = st.session_state.get("last_query", "")
    symbols = st.session_state.get("last_symbols") or []
    show_steps = st.session_state.get("show_steps", True)
    show_viz = st.session_state.get("show_viz", True)

    st.divider()
    m1, m2 = st.columns([3, 1])
    with m1:
        st.markdown(f"**Query:** {query}")
    with m2:
        st.markdown(f"**Symbols:** {', '.join(symbols) if symbols else 'none'}")

    # --- Dashboard layer ---
    if show_viz:
        try:
            _render_kpi_dashboard(symbols)
            _render_charts(symbols)
        except Exception as e:
            st.warning(f"Visualization layer error: {e}")

    st.divider()

    # --- Narrative layer ---
    st.subheader("Research note")
    report = result.get("final_report") or "_No report generated_"
    view = st.radio(
        "Report layout",
        ["Section tabs (recommended)", "Single scroll"],
        horizontal=True,
        label_visibility="collapsed",
    )
    if view.startswith("Section"):
        _render_report_structured(report)
    else:
        st.markdown(report)

    with st.expander("Data sources", expanded=False):
        sources_md = result.get("data_sources_md")
        if not sources_md:
            from pruinsight.report_export import build_sources_section

            sources_md = build_sources_section(query, symbols)
        st.markdown(sources_md)

    st.markdown("##### Export")
    _render_downloads(report)

    st.divider()
    _render_agent_intermediates(result, show_steps)

    st.caption(
        "Disclaimer: AI-generated educational demo only. Not investment advice "
        "and not an official ICICI Prudential AMC product. "
        "Charts use Yahoo Finance data which may be delayed or incomplete."
    )


if __name__ == "__main__":
    main()

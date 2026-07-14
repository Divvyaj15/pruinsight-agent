"""
PruInsight Streamlit frontend.

Run:
    .venv\\Scripts\\python.exe -m streamlit run streamlit_app.py
"""

from __future__ import annotations

import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="PruInsight | Multi-Agent Research",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Light custom styling
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; max-width: 1100px; }
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
    div[data-testid="stStatusWidget"] { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

PIPELINE_STEPS = [
    ("researcher", "Market Researcher", "Web/news search, company headlines, indices"),
    ("filings", "Filings Analyst", "SEBI/BSE/NSE/IR PDFs + BM25 RAG"),
    ("fundamentals", "Fundamentals Analyst", "Quote, financials, history, peers, Street view"),
    ("mf_context", "MF Context (AMFI)", "AMFI NAVs + fund factsheet RAG"),
    ("risk", "Risk Assessor", "Downside risks + vol / VIX context"),
    ("synthesizer", "Report Synthesizer", "Final MF-desk note"),
]

TOOL_CATALOG = [
    ("web_search", "Tavily — broad web research"),
    ("news_search", "Tavily news topic — recent articles"),
    ("get_company_news", "Yahoo Finance company headlines"),
    ("search_company_filings", "Find annual reports / results / exchange docs"),
    ("ingest_filing_pdf", "Download PDF + chunk into RAG store"),
    ("query_filings_rag", "BM25 retrieve excerpts from ingested PDFs"),
    ("search_amfi_schemes", "AMFI scheme search (official NAVAll)"),
    ("get_amfi_nav", "AMFI latest NAV by code/name"),
    ("search_related_equity_funds", "Theme → equity schemes + NAV"),
    ("search_fund_factsheet", "Find AMC factsheet PDFs"),
    ("ingest_fund_factsheet_pdf", "Factsheet PDF → factsheet RAG store"),
    ("query_factsheet_rag", "BM25 retrieve factsheet excerpts"),
    ("get_stock_data", "NSE quote + valuation metrics"),
    ("get_financials", "Annual income / BS / cash flow"),
    ("get_price_history", "Returns & volatility"),
    ("get_analyst_view", "Targets & recommendations"),
    ("get_index_snapshot", "NIFTY, Bank Nifty, India VIX, Sensex, USDINR"),
    ("get_peer_snapshot", "Multi-name relative metrics"),
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


def _parse_symbols(raw: str) -> list[str]:
    if not raw or not raw.strip():
        return []
    parts = [p.strip().upper().replace(".NS", "") for p in raw.replace(";", ",").split(",")]
    return [p for p in parts if p]


def _keys_status() -> tuple[bool, bool]:
    groq = bool(os.getenv("GROQ_API_KEY"))
    tavily = bool(os.getenv("TAVILY_API_KEY"))
    return groq, tavily


@st.cache_resource(show_spinner=False)
def _get_runner():
    from pruinsight.runner import run_research

    return run_research


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### PruInsight")
        st.caption("Multi-agent equity research for a mutual-fund desk (demo).")

        groq_ok, tavily_ok = _keys_status()
        st.markdown("**API keys**")
        st.write(("✅" if groq_ok else "❌") + " `GROQ_API_KEY`")
        st.write(("✅" if tavily_ok else "❌") + " `TAVILY_API_KEY`")
        if not (groq_ok and tavily_ok):
            st.warning("Add missing keys to `.env` and restart Streamlit.")

        st.divider()
        st.markdown("**Pipeline**")
        for _, name, desc in PIPELINE_STEPS:
            st.markdown(f"**{name}**  \n<span class='pru-muted'>{desc}</span>", unsafe_allow_html=True)

        st.divider()
        st.markdown("**Research tools**")
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


def main() -> None:
    _render_sidebar()

    st.title("PruInsight Research Desk")
    st.markdown(
        '<span class="pru-badge">LangGraph</span>'
        '<span class="pru-badge">Groq</span>'
        '<span class="pru-badge">Tavily</span>'
        '<span class="pru-badge">yfinance</span>',
        unsafe_allow_html=True,
    )
    st.write(
        "Run the multi-agent pipeline: "
        "**Researcher → Filings → Fundamentals → MF Context (AMFI) → Risk → Synthesizer**."
    )

    # Defaults for widgets
    if "query_input" not in st.session_state:
        st.session_state["query_input"] = EXAMPLES["HDFC Bank (MF view)"]["query"]
    if "symbols_input" not in st.session_state:
        st.session_state["symbols_input"] = EXAMPLES["HDFC Bank (MF view)"]["symbols"]

    with st.form("research_form", clear_on_submit=False):
        query = st.text_area(
            "Research query",
            key="query_input",
            height=100,
            placeholder="e.g. Latest insights on HDFC Bank for mutual fund perspective",
        )
        col1, col2 = st.columns([2, 1])
        with col1:
            symbols_raw = st.text_input(
                "NSE symbols (optional, comma-separated)",
                key="symbols_input",
                placeholder="HDFCBANK, RELIANCE",
                help="Bare NSE tickers without .NS suffix",
            )
        with col2:
            show_steps = st.checkbox("Show agent intermediates", value=True)

        submitted = st.form_submit_button(
            "Generate research note",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not query or not query.strip():
            st.error("Please enter a research query.")
            return

        groq_ok, tavily_ok = _keys_status()
        if not groq_ok:
            st.error("`GROQ_API_KEY` is missing from the environment / `.env`.")
            return
        if not tavily_ok:
            st.error("`TAVILY_API_KEY` is missing from the environment / `.env`.")
            return

        symbols = _parse_symbols(symbols_raw)
        run_research = _get_runner()

        progress = st.progress(0, text="Starting multi-agent pipeline…")
        status = st.empty()

        # Sequential progress UI while the (blocking) graph runs
        # LangGraph invoke is one shot; we stage UX then fill results after.
        status.info(
            "Agents running: researcher → filings → fundamentals → mf_context → risk → synthesizer …"
        )
        progress.progress(10, text="Researcher + filings + AMFI MF context …")

        try:
            with st.spinner("Running multi-agent graph (may take 20–60s)…"):
                result = run_research(query, symbols)
        except Exception as e:
            progress.empty()
            status.empty()
            st.error(f"Pipeline failed: {e}")
            with st.expander("Error details"):
                st.exception(e)
            return

        progress.progress(100, text="Done")
        status.success("Research note ready.")

        st.session_state["last_result"] = result
        st.session_state["last_query"] = query
        st.session_state["last_symbols"] = symbols
        st.session_state["show_steps"] = show_steps

    # Render last result if present
    result = st.session_state.get("last_result")
    if not result:
        st.info("Enter a query and click **Generate research note** to begin.")
        return

    query = st.session_state.get("last_query", "")
    symbols = st.session_state.get("last_symbols") or []
    show_steps = st.session_state.get("show_steps", True)

    st.divider()
    meta1, meta2 = st.columns(2)
    with meta1:
        st.markdown(f"**Query:** {query}")
    with meta2:
        st.markdown(f"**Symbols:** {', '.join(symbols) if symbols else 'auto / none'}")

    if show_steps:
        st.subheader("Agent intermediates")
        tabs = st.tabs(
            [
                "Market Research",
                "Filings",
                "Fundamentals",
                "MF / AMFI",
                "Risk",
                "Pipeline",
            ]
        )
        with tabs[0]:
            st.markdown(result.get("market_research") or "_No output_")
        with tabs[1]:
            st.markdown(result.get("filings_context") or "_No output_")
        with tabs[2]:
            st.markdown(result.get("fundamentals") or "_No output_")
        with tabs[3]:
            st.markdown(result.get("mf_context") or "_No output_")
        with tabs[4]:
            st.markdown(result.get("risk_assessment") or "_No output_")
        with tabs[5]:
            for i, (_, name, desc) in enumerate(PIPELINE_STEPS, 1):
                st.markdown(f"{i}. **{name}** — {desc}")

    st.subheader("Final PruInsight note")
    report = result.get("final_report") or "_No report generated_"
    st.markdown(report)

    # Data sources are appended at the bottom of the report; also surface clearly
    with st.expander("Data sources (where this note’s data was collected)", expanded=False):
        sources_md = result.get("data_sources_md")
        if not sources_md:
            from pruinsight.report_export import build_sources_section

            sources_md = build_sources_section(query, symbols)
        st.markdown(sources_md)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"pruinsight_note_{stamp}"

    pdf_bytes = None
    pdf_error = None
    try:
        from pruinsight.report_export import report_to_pdf_bytes

        pdf_bytes = report_to_pdf_bytes(
            report,
            title="PruInsight Research Note",
        )
    except Exception as e:
        pdf_error = str(e)

    dl1, dl2 = st.columns(2)
    with dl1:
        st.download_button(
            label="Download note (.md)",
            data=report,
            file_name=f"{base}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with dl2:
        if pdf_bytes:
            st.download_button(
                label="Download note (.pdf)",
                data=pdf_bytes,
                file_name=f"{base}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            st.button(
                "PDF unavailable",
                disabled=True,
                use_container_width=True,
                help=pdf_error or "Install fpdf2: pip install fpdf2",
            )
            if pdf_error:
                st.caption(f"PDF export error: {pdf_error}")

    st.caption(
        "Disclaimer: AI-generated educational demo only. Not investment advice "
        "and not an official ICICI Prudential AMC product. "
        "Sources are listed at the bottom of the note and in the expander above."
    )


if __name__ == "__main__":
    main()

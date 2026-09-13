"""
PruInsight Streamlit frontend — mutual-fund research desk.

Run:
    .venv\\Scripts\\python.exe -m streamlit run streamlit_app.py
"""

from __future__ import annotations

import os
import re
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from pruinsight.ui_theme import (
    THEME_CSS,
    kpi_cards_html,
    masthead_html,
    note_masthead_html,
    pipeline_html,
    query_bar_html,
    sidebar_brand_html,
    status_grid_html,
    workpaper_pills_html,
)

load_dotenv()


def _streamlit_secrets_to_env() -> None:
    """Streamlit Cloud stores secrets in TOML (`st.secrets`), not `.env`.

    Copy them into os.environ so Groq/Tavily/LangSmith keep using getenv().
    """
    try:
        secrets = st.secrets
    except Exception:
        return
    for key, value in secrets.items():
        if isinstance(value, dict):
            for inner_key, inner_val in value.items():
                if inner_val is not None and str(inner_val).strip() != "":
                    os.environ[str(inner_key)] = str(inner_val)
        elif value is not None and str(value).strip() != "":
            os.environ[str(key)] = str(value)


st.set_page_config(
    page_title="PruInsight · Research Desk",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "PruInsight — multi-agent equity research desk. Educational demo only.",
    },
)

_streamlit_secrets_to_env()

st.markdown(f"<style>{THEME_CSS}</style>", unsafe_allow_html=True)

PIPELINE_STEPS = [
    ("researcher", "Market", "Web/news search, company headlines, indices"),
    ("filings", "Filings", "SEBI/BSE/NSE/IR PDFs + BM25 RAG"),
    ("transcripts", "Transcripts", "Earnings call transcripts + BM25 RAG"),
    ("fundamentals", "Fundamentals", "Screener-style ratios, quarterly, holders, peers"),
    ("mf_context", "MF / AMFI", "AMFI NAVs + fund factsheet RAG"),
    ("macro", "Macro", "RBI policy + India/global macro (FRED optional)"),
    ("risk", "Risk", "Downside risks + vol / VIX context"),
    ("synthesizer", "Synthesizer", "Final MF-desk note"),
]

TOOL_CATALOG = [
    ("web_search", "Tavily → Serper → DuckDuckGo cascade"),
    ("search_company_filings / transcripts", "Primary docs + earnings RAG"),
    ("get_screener_style_snapshot", "Deep ratios + quarterly + holders"),
    ("search_amfi_schemes", "AMFI official NAV universe"),
    ("get_macro_dashboard", "India + global macro pack"),
]

EXAMPLES = {
    "HDFC Bank": {
        "query": "Latest insights on HDFC Bank for mutual fund perspective",
        "symbols": "HDFCBANK",
        "blurb": "Private-bank franchise, asset quality, and MF sizing.",
    },
    "Reliance": {
        "query": "Outlook on Reliance Industries for large-cap funds",
        "symbols": "RELIANCE",
        "blurb": "Energy-to-retail conglomerate for large-cap desks.",
    },
    "Private banks": {
        "query": "Compare private sector banks for diversified equity funds",
        "symbols": "HDFCBANK, ICICIBANK, KOTAKBANK",
        "blurb": "Side-by-side HDFC, ICICI, and Kotak.",
    },
    "IT majors": {
        "query": "TCS vs Infosys — mutual fund holding considerations",
        "symbols": "TCS, INFY",
        "blurb": "Quality IT compounders and relative valuation.",
    },
}

AGENT_FIELDS = [
    ("market_research", "Market", "researcher"),
    ("filings_context", "Filings", "filings"),
    ("transcripts_context", "Transcripts", "transcripts"),
    ("fundamentals", "Fundamentals", "fundamentals"),
    ("mf_context", "MF / AMFI", "mf_context"),
    ("macro_context", "Macro", "macro"),
    ("risk_assessment", "Risk", "risk"),
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


def _langsmith_status() -> dict:
    try:
        from pruinsight.tracing import configure_tracing, tracing_status

        configure_tracing()
        return tracing_status()
    except Exception:
        return {"enabled": False, "has_api_key": False, "project": "pruinsight-agent"}


@st.cache_resource(show_spinner=False)
def _get_stream_runner():
    from pruinsight.tracing import configure_tracing

    configure_tracing()
    from pruinsight.runner import stream_research

    return stream_research


@st.cache_data(ttl=120, show_spinner=False)
def _cached_tape():
    from pruinsight.viz_data import fetch_index_tape

    try:
        return fetch_index_tape()
    except Exception:
        return []


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


def _styled_line_chart(chart_df):
    import altair as alt

    long = chart_df.reset_index()
    date_col = long.columns[0]
    long = long.rename(columns={date_col: "Date"})
    long = long.melt("Date", var_name="Symbol", value_name="Close").dropna()
    if long.empty:
        return None
    palette = ["#0B1C2C", "#C4A35A", "#2A6F7F", "#8C4A3A"]
    return (
        alt.Chart(long)
        .mark_line(strokeWidth=2.2)
        .encode(
            x=alt.X("Date:T", title=None, axis=alt.Axis(grid=False, labelColor="#6B7785")),
            y=alt.Y(
                "Close:Q",
                title="Close (₹)",
                scale=alt.Scale(zero=False),
                axis=alt.Axis(grid=True, gridColor="#E4DDD0", labelColor="#6B7785", titleColor="#15202B"),
            ),
            color=alt.Color(
                "Symbol:N",
                scale=alt.Scale(range=palette),
                legend=alt.Legend(orient="top", title=None, labelColor="#15202B"),
            ),
            tooltip=[
                alt.Tooltip("Date:T", title="Date"),
                "Symbol:N",
                alt.Tooltip("Close:Q", title="Close", format=",.2f"),
            ],
        )
        .properties(height=320)
        .configure_view(stroke=None)
        .configure_axis(domainColor="#C4B8A0")
    )


def _styled_bar_chart(plot_df, metric: str):
    import altair as alt

    df = plot_df.reset_index()
    if df.empty:
        return None
    x_name = df.columns[0]
    return (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, color="#C4A35A")
        .encode(
            x=alt.X(f"{x_name}:N", title=None, sort="-y", axis=alt.Axis(labelColor="#15202B", labelAngle=0)),
            y=alt.Y(
                f"{metric}:Q",
                title=metric,
                axis=alt.Axis(grid=True, gridColor="#E4DDD0", labelColor="#6B7785", titleColor="#15202B"),
            ),
            tooltip=[x_name, alt.Tooltip(f"{metric}:Q", format=",.2f")],
        )
        .properties(height=320)
        .configure_view(stroke=None)
        .configure_axis(domainColor="#C4B8A0")
    )


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown(sidebar_brand_html(), unsafe_allow_html=True)
        st.caption("Equity research for a mutual-fund desk. Educational demo.")

        keys = _keys_status()
        ls = _langsmith_status()
        st.markdown("**System status**")
        st.markdown(
            status_grid_html(keys, bool(ls.get("enabled"))),
            unsafe_allow_html=True,
        )
        if ls.get("enabled"):
            st.caption(f"Traces · `{ls.get('project')}` · smith.langchain.com")
        if not keys["groq"]:
            st.warning("Add `GROQ_API_KEY` to `.env` and restart.")
        else:
            st.caption("Search cascade: Tavily → Serper → DuckDuckGo")

        try:
            from pruinsight.llm import model_roster

            with st.expander("LLM models by role"):
                for role, mid in model_roster().items():
                    st.caption(f"**{role}:** `{mid}`")
        except Exception:
            pass

        st.divider()
        st.markdown("**Eight-agent pipeline**")
        st.markdown(
            pipeline_html(PIPELINE_STEPS),
            unsafe_allow_html=True,
        )
        with st.expander("What each agent does"):
            for i, (_, name, desc) in enumerate(PIPELINE_STEPS, 1):
                st.caption(f"{i:02d}  **{name}** — {desc}")

        with st.expander("Research tools"):
            for tool_name, tool_desc in TOOL_CATALOG:
                st.caption(f"`{tool_name}` — {tool_desc}")

        st.divider()
        st.markdown("**Desk presets**")
        choice = st.selectbox("Load a starting brief", ["—"] + list(EXAMPLES.keys()))
        if choice != "—" and st.button("Apply preset", use_container_width=True):
            ex = EXAMPLES[choice]
            st.session_state["query_input"] = ex["query"]
            st.session_state["symbols_input"] = ex["symbols"]
            st.rerun()

        if st.session_state.get("last_result") and st.button(
            "Clear last note", use_container_width=True
        ):
            for k in (
                "last_result",
                "last_query",
                "last_symbols",
                "last_run_at",
                "show_steps",
                "show_viz",
            ):
                st.session_state.pop(k, None)
            st.rerun()

        st.divider()
        st.caption("Not investment advice · Educational demo only")


def _render_kpi_dashboard(symbols: list[str]) -> None:
    if not symbols:
        st.info("Pass NSE symbols on the brief to unlock live KPI cards and charts.")
        return

    from pruinsight.viz_data import day_change_pct, format_inr_cr, format_num

    cards = []
    for sym in symbols[:4]:
        try:
            snap = _cached_snapshot(sym)
        except Exception as e:
            st.warning(f"Could not load snapshot for {sym}: {e}")
            continue
        chg = day_change_pct(snap)
        lo, hi, px = snap.get("low_52w"), snap.get("high_52w"), snap.get("price")
        pos = None
        if lo and hi and px and hi > lo:
            pos = (px - lo) / (hi - lo)
        cards.append(
            {
                "symbol": snap["symbol"],
                "name": snap["name"],
                "sector": snap.get("sector") or "",
                "price_s": f"₹{format_num(snap['price'], decimals=2)}"
                if snap.get("price")
                else "N/A",
                "chg": chg,
                "metrics": [
                    ("P/E", format_num(snap.get("pe"))),
                    ("P/B", format_num(snap.get("pb"))),
                    ("ROE", format_num(snap.get("roe"), "%", 1)),
                    ("Mkt cap", format_inr_cr(snap.get("market_cap"))),
                    ("Div yld", format_num(snap.get("div_yield"), "%", 2)),
                    ("Beta", format_num(snap.get("beta"))),
                    ("vs 52w hi", format_num(snap.get("vs_high_pct"), "%", 1)),
                    ("vs 52w lo", format_num(snap.get("vs_low_pct"), "%", 1)),
                ],
                "range_pos": pos,
                "low_s": format_num(lo, decimals=2) if lo else "—",
                "high_s": format_num(hi, decimals=2) if hi else "—",
                "tgt_s": format_num(snap.get("target_mean"), decimals=2)
                if snap.get("target_mean")
                else None,
            }
        )
    if cards:
        st.markdown(kpi_cards_html(cards), unsafe_allow_html=True)


def _render_charts(symbols: list[str]) -> None:
    if not symbols:
        return

    left, right = st.columns(2)
    with left:
        st.markdown("**Price history**")
        period = st.selectbox(
            "Lookback",
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
                chart_df = frames[0]
                for extra in frames[1:]:
                    chart_df = chart_df.join(extra, how="outer")
                chart = _styled_line_chart(chart_df)
                if chart is not None:
                    st.altair_chart(chart, use_container_width=True)
                else:
                    st.caption("No price history available.")
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
                    chart = _styled_bar_chart(plot_df, metric)
                    if chart is not None:
                        st.altair_chart(chart, use_container_width=True)
                with st.expander("Peer table"):
                    st.dataframe(peer_df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.caption(f"Peer chart unavailable: {e}")


def _render_report_structured(report: str) -> None:
    from pruinsight.viz_data import parse_report_sections

    sections = parse_report_sections(report)
    if not sections:
        st.markdown('<div class="note-body-anchor"></div>', unsafe_allow_html=True)
        st.markdown(report)
        return

    labels = [h if len(h) <= 28 else h[:25] + "…" for h, _ in sections]
    tabs = st.tabs(labels)
    for tab, (heading, body) in zip(tabs, sections):
        with tab:
            st.markdown('<div class="note-body-anchor"></div>', unsafe_allow_html=True)
            st.markdown(f"#### {heading}")
            if body:
                st.markdown(body)
            else:
                st.caption("_Empty section_")

    with st.expander("Full note (single page)", expanded=False):
        st.markdown(report)


def _render_agent_intermediates(result: dict, show_steps: bool) -> None:
    if not show_steps:
        return

    st.markdown("### Agent workpapers")
    st.caption("Intermediate briefs written by each specialist before synthesis.")

    pills = []
    for key, label, _ in AGENT_FIELDS:
        text = result.get(key) or ""
        pills.append((label, len(text.strip()) > 40))
    synth = result.get("final_report") or ""
    pills.append(("Note", len(synth.strip()) > 80))
    st.markdown(workpaper_pills_html(pills), unsafe_allow_html=True)

    tabs = st.tabs([label for _, label, _ in AGENT_FIELDS] + ["Pipeline"])
    for i, (key, label, _) in enumerate(AGENT_FIELDS):
        with tabs[i]:
            content = result.get(key) or "_No output from this agent._"
            st.markdown(content)
    with tabs[-1]:
        st.markdown(
            pipeline_html(
                PIPELINE_STEPS,
                done=[k for k, _, _ in PIPELINE_STEPS],
            ),
            unsafe_allow_html=True,
        )
        for i, (_, name, desc) in enumerate(PIPELINE_STEPS, 1):
            st.markdown(f"**{i:02d} · {name}** — {desc}")


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
            "Markdown",
            data=report,
            file_name=f"{base}.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with d2:
        if pdf_bytes:
            st.download_button(
                "PDF",
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
        plain = re.sub(r"[#*_`]", "", report)
        st.download_button(
            "Plain text",
            data=plain,
            file_name=f"{base}.txt",
            mime="text/plain",
            use_container_width=True,
        )


def _render_landing() -> None:
    st.markdown("#### Start from a desk preset")
    cols = st.columns(4)
    for col, (name, ex) in zip(cols, EXAMPLES.items()):
        with col:
            st.markdown(
                f"<div class='hero-card'><h4>{name}</h4>"
                f"<p>{ex['blurb']}</p>"
                f"<p style='margin-top:0.45rem;font-size:0.78rem;color:#6B7785'>"
                f"<b>{ex['symbols']}</b></p></div>",
                unsafe_allow_html=True,
            )
            if st.button(f"Load {name}", key=f"preset_{name}", use_container_width=True):
                st.session_state["query_input"] = ex["query"]
                st.session_state["symbols_input"] = ex["symbols"]
                st.rerun()

    st.markdown("#### How a run works")
    st.markdown(
        pipeline_html(PIPELINE_STEPS),
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            "<div class='hero-card'><h4>Live market layer</h4>"
            "<p>KPI cards, 52-week range, and peer charts come from Yahoo Finance — "
            "independent of the LLM narrative.</p></div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            "<div class='hero-card'><h4>Primary-source agents</h4>"
            "<p>Filings, transcripts, and fund factsheets are searched, ingested, "
            "and retrieved with BM25 before the note is written.</p></div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            "<div class='hero-card'><h4>MF-desk synthesis</h4>"
            "<p>The last agent writes a structured note with horizon, sizing, "
            "monitoring, and a disclaimer — exportable as Markdown or PDF.</p></div>",
            unsafe_allow_html=True,
        )


def _run_pipeline(query: str, symbols: list[str], show_steps: bool, show_viz: bool) -> None:
    stream_research = _get_stream_runner()
    pipe_slot = st.empty()
    status_slot = st.empty()
    labels = {k: n for k, n, _ in PIPELINE_STEPS}

    pipe_slot.markdown(
        pipeline_html(PIPELINE_STEPS, done=[], active="researcher"),
        unsafe_allow_html=True,
    )
    status_slot.info("Opening the eight-agent graph… typically 1–3 minutes.")

    result = None
    try:
        for evt in stream_research(query, symbols, source="streamlit"):
            kind = evt.get("event")
            if kind == "start":
                pipe_slot.markdown(
                    pipeline_html(PIPELINE_STEPS, done=[], active=evt.get("active")),
                    unsafe_allow_html=True,
                )
                status_slot.info("Market researcher is gathering news and headlines…")
            elif kind == "node_done":
                node = evt.get("node")
                nxt = evt.get("active")
                pipe_slot.markdown(
                    pipeline_html(
                        PIPELINE_STEPS,
                        done=evt.get("done") or [],
                        active=nxt,
                    ),
                    unsafe_allow_html=True,
                )
                if nxt:
                    status_slot.info(
                        f"**{labels.get(node, node)}** complete · running **{labels.get(nxt, nxt)}**…"
                    )
                else:
                    status_slot.info("Synthesizing the research note…")
            elif kind == "done":
                result = evt.get("result")
    except Exception as e:
        pipe_slot.empty()
        status_slot.empty()
        st.error(f"Pipeline failed: {e}")
        with st.expander("Error details"):
            st.exception(e)
        return

    if not result:
        pipe_slot.empty()
        status_slot.error("Pipeline finished without a result.")
        return

    pipe_slot.markdown(
        pipeline_html(
            PIPELINE_STEPS,
            done=[k for k, _, _ in PIPELINE_STEPS],
            active=None,
        ),
        unsafe_allow_html=True,
    )
    ls = (result or {}).get("langsmith") or {}
    if ls.get("enabled"):
        status_slot.success(
            f"Research note ready · LangSmith project `{ls.get('project')}`"
        )
    else:
        status_slot.success("Research note ready.")

    st.session_state["last_result"] = result
    st.session_state["last_query"] = query
    st.session_state["last_symbols"] = symbols
    st.session_state["show_steps"] = show_steps
    st.session_state["show_viz"] = show_viz
    st.session_state["last_run_at"] = datetime.now().strftime("%d %b %Y · %H:%M")


def main() -> None:
    _render_sidebar()

    tape = _cached_tape()
    st.markdown(masthead_html(tape), unsafe_allow_html=True)
    st.markdown(
        "<p class='pru-lede'>Compose a brief. Eight specialist agents gather "
        "<strong>news, filings, transcripts, fundamentals, AMFI context, macro, and risk</strong>, "
        "then synthesize a mutual-fund desk note.</p>",
        unsafe_allow_html=True,
    )

    if "query_input" not in st.session_state:
        st.session_state["query_input"] = EXAMPLES["HDFC Bank"]["query"]
    if "symbols_input" not in st.session_state:
        st.session_state["symbols_input"] = EXAMPLES["HDFC Bank"]["symbols"]

    with st.form("research_form", clear_on_submit=False):
        query = st.text_area(
            "Research question",
            key="query_input",
            height=92,
            placeholder="e.g. Latest insights on HDFC Bank for mutual fund perspective",
        )
        col1, col2, col3 = st.columns([2.2, 1, 1])
        with col1:
            symbols_raw = st.text_input(
                "NSE symbols",
                key="symbols_input",
                placeholder="HDFCBANK, ICICIBANK",
                help="Bare tickers without .NS — unlocks KPI cards and charts",
            )
        with col2:
            show_steps = st.checkbox("Agent workpapers", value=True)
        with col3:
            show_viz = st.checkbox("Charts & KPIs", value=True)

        submitted = st.form_submit_button(
            "Run research pipeline",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not query or not query.strip():
            st.error("Please enter a research question.")
            return
        keys = _keys_status()
        if not keys["groq"]:
            st.error("`GROQ_API_KEY` is missing from `.env`.")
            return
        if not keys["tavily"] and not keys["serper"] and not keys["duckduckgo"]:
            st.error("No search backend. Set Tavily/Serper or install `ddgs`.")
            return
        symbols = _parse_symbols(symbols_raw)
        _run_pipeline(query, symbols, show_steps, show_viz)

    result = st.session_state.get("last_result")
    if not result:
        _render_landing()
        st.markdown(
            "<div class='desk-foot'>Disclaimer: AI-generated educational demo only. "
            "Not investment advice and not an official ICICI Prudential AMC product. "
            "Market tape and charts use Yahoo Finance data which may be delayed or incomplete.</div>",
            unsafe_allow_html=True,
        )
        return

    query = st.session_state.get("last_query", "")
    symbols = st.session_state.get("last_symbols") or []
    show_steps = st.session_state.get("show_steps", True)
    show_viz = st.session_state.get("show_viz", True)
    when = st.session_state.get("last_run_at") or datetime.now().strftime("%d %b %Y")

    st.markdown(query_bar_html(query, symbols, when), unsafe_allow_html=True)

    overview, charts, note, papers, export = st.tabs(
        ["Overview", "Charts", "Research note", "Workpapers", "Export & sources"]
    )

    with overview:
        if show_viz:
            try:
                _render_kpi_dashboard(symbols)
            except Exception as e:
                st.warning(f"Visualization layer error: {e}")
        else:
            st.caption("Charts & KPIs were turned off for this run.")
        report_preview = result.get("final_report") or ""
        from pruinsight.viz_data import parse_report_sections

        sections = parse_report_sections(report_preview)
        exec_body = ""
        for h, b in sections:
            if "executive" in h.lower() or h.lower() in {"overview", "summary"}:
                exec_body = b
                break
        if not exec_body and sections:
            exec_body = sections[0][1]
        if exec_body:
            st.markdown("##### Executive snapshot")
            st.markdown('<div class="note-body-anchor"></div>', unsafe_allow_html=True)
            st.markdown(exec_body[:1800] + ("…" if len(exec_body) > 1800 else ""))

    with charts:
        if show_viz:
            try:
                _render_charts(symbols)
            except Exception as e:
                st.warning(f"Chart layer error: {e}")
        else:
            st.caption("Charts were turned off for this run.")

    with note:
        report = result.get("final_report") or "_No report generated_"
        st.markdown(
            note_masthead_html(
                "Mutual-fund desk note",
                f"{when}\nSymbols: {', '.join(symbols) if symbols else '—'}",
            ),
            unsafe_allow_html=True,
        )
        view = st.radio(
            "Note layout",
            ["Section tabs", "Single scroll"],
            horizontal=True,
            label_visibility="collapsed",
        )
        if view.startswith("Section"):
            _render_report_structured(report)
        else:
            st.markdown('<div class="note-body-anchor"></div>', unsafe_allow_html=True)
            st.markdown(report)

    with papers:
        _render_agent_intermediates(result, show_steps)
        if not show_steps:
            st.caption("Workpapers were turned off for this run. Re-run with the toggle on.")

    with export:
        st.markdown("##### Export this note")
        report = result.get("final_report") or ""
        _render_downloads(report)
        st.markdown("##### Data sources")
        sources_md = result.get("data_sources_md")
        if not sources_md:
            from pruinsight.report_export import build_sources_section

            sources_md = build_sources_section(query, symbols)
        st.markdown(sources_md)

    st.markdown(
        "<div class='desk-foot'>Disclaimer: AI-generated educational demo only. "
        "Not investment advice and not an official ICICI Prudential AMC product. "
        "Market tape and charts use Yahoo Finance data which may be delayed or incomplete.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()

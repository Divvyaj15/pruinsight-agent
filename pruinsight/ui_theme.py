"""PruInsight research-desk visual system (CSS + HTML fragments)."""

from __future__ import annotations

import html
from typing import Any, Optional

LOGO_SVG = """
<svg class="pru-mark" viewBox="0 0 40 40" width="36" height="36" aria-hidden="true">
  <rect width="40" height="40" rx="10" fill="#0B1C2C"/>
  <polyline points="8,28 15,20 20,24 32,10" fill="none" stroke="#D4AF67"
            stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="32" cy="10" r="2.6" fill="#F6E7C1"/>
</svg>
""".strip()

THEME_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,700&family=IBM+Plex+Sans:wght@400;500;600;700&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap');

:root {
  --navy-950: #061018;
  --navy-900: #0B1C2C;
  --navy-800: #12263A;
  --navy-700: #1A3650;
  --gold-200: #F6E7C1;
  --gold-400: #D4AF67;
  --gold-500: #C4A35A;
  --gold-600: #A6853F;
  --paper: #F4F0E6;
  --paper-2: #EBE4D6;
  --ink: #15202B;
  --ink-soft: #3D4D5C;
  --muted: #6B7785;
  --line: #E4DDD0;
  --card: #FFFdf8;
  --up: #1F8A5B;
  --down: #C0392B;
}

html, body, [data-testid="stAppViewContainer"], .stApp {
  background: var(--paper) !important;
  color: var(--ink);
  font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
}

.stApp {
  background:
    radial-gradient(1200px 420px at 8% -10%, rgba(196,163,90,0.14), transparent 55%),
    radial-gradient(900px 380px at 100% 0%, rgba(11,28,44,0.08), transparent 50%),
    var(--paper) !important;
}

#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], .stDeployButton { display: none !important; }

header[data-testid="stHeader"] {
  background: transparent !important;
  height: 0 !important;
}

.block-container {
  padding-top: 1.15rem !important;
  padding-bottom: 3.5rem !important;
  max-width: 1280px !important;
}

/* ----- Sidebar: dark console ----- */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, var(--navy-950) 0%, var(--navy-900) 55%, #0E2436 100%) !important;
  border-right: 1px solid rgba(212,175,103,0.18) !important;
}
section[data-testid="stSidebar"] > div { background: transparent !important; }
section[data-testid="stSidebar"] * { color: #E8E0D0 !important; }
section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] small {
  color: #A9B4C0 !important;
}
section[data-testid="stSidebar"] hr {
  border-color: rgba(232,224,208,0.12) !important;
}
section[data-testid="stSidebar"] [data-testid="stExpander"] {
  background: rgba(255,255,255,0.04) !important;
  border: 1px solid rgba(212,175,103,0.16) !important;
  border-radius: 10px !important;
}
section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div {
  background: rgba(255,255,255,0.06) !important;
  border-color: rgba(212,175,103,0.28) !important;
  color: #F4F0E6 !important;
}
section[data-testid="stSidebar"] .stButton button {
  background: transparent !important;
  color: var(--gold-200) !important;
  border: 1px solid rgba(212,175,103,0.45) !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
}
section[data-testid="stSidebar"] .stButton button:hover {
  background: rgba(212,175,103,0.12) !important;
  border-color: var(--gold-400) !important;
}

/* ----- Form / inputs ----- */
div[data-testid="stForm"] {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 0.35rem 0.4rem 0.7rem 0.4rem;
  box-shadow: 0 12px 40px rgba(11,28,44,0.06);
  border-top: 3px solid var(--gold-500);
}
.stTextArea textarea, .stTextInput input {
  background: #FBFAF6 !important;
  border-radius: 10px !important;
  border: 1px solid var(--line) !important;
  color: var(--ink) !important;
  font-family: "IBM Plex Sans", sans-serif !important;
}
.stTextArea textarea:focus, .stTextInput input:focus {
  border-color: var(--gold-500) !important;
  box-shadow: 0 0 0 3px rgba(196,163,90,0.18) !important;
}
.stFormSubmitButton button {
  background: linear-gradient(180deg, #D4AF67 0%, #B8923E 100%) !important;
  color: var(--navy-900) !important;
  border: none !important;
  font-weight: 700 !important;
  letter-spacing: 0.06em !important;
  text-transform: uppercase !important;
  height: 3.05rem !important;
  border-radius: 12px !important;
  font-size: 0.92rem !important;
}
.stFormSubmitButton button:hover {
  filter: brightness(1.05);
  box-shadow: 0 8px 22px rgba(184,146,62,0.35) !important;
}

.stButton button {
  border-radius: 10px !important;
  font-weight: 600 !important;
}
div[data-testid="stDownloadButton"] button {
  background: var(--navy-900) !important;
  color: #F6E7C1 !important;
  border: 1px solid rgba(212,175,103,0.4) !important;
  border-radius: 10px !important;
  font-weight: 600 !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
  gap: 0.15rem;
  background: transparent;
  border-bottom: 1px solid var(--line);
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  color: var(--muted) !important;
  font-weight: 600 !important;
  padding: 0.65rem 0.9rem !important;
}
.stTabs [aria-selected="true"] {
  color: var(--navy-900) !important;
  border-bottom: 2px solid var(--gold-500) !important;
}

.stExpander {
  background: var(--card) !important;
  border: 1px solid var(--line) !important;
  border-radius: 12px !important;
}

[data-testid="stAlert"] { border-radius: 12px !important; }

/* ----- Brand fragments ----- */
.pru-masthead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.25rem;
  background: linear-gradient(105deg, #061018 0%, #0B1C2C 48%, #16324A 100%);
  color: #F4F0E6;
  border-radius: 18px;
  padding: 1.05rem 1.3rem;
  margin-bottom: 1.1rem;
  border: 1px solid rgba(212,175,103,0.22);
  box-shadow: 0 16px 40px rgba(6,16,24,0.18);
}
.pru-brand {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  min-width: 220px;
}
.pru-brand .name {
  font-family: Fraunces, Georgia, serif;
  font-size: 1.55rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.1;
  color: #F7F1E4;
}
.pru-brand .sub {
  font-size: 0.68rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--gold-400);
  font-weight: 600;
  margin-top: 0.12rem;
}
.pru-tape {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 0.55rem;
}
.pru-chip {
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(212,175,103,0.2);
  border-radius: 10px;
  padding: 0.38rem 0.7rem;
  min-width: 118px;
}
.pru-chip .k {
  font-size: 0.62rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #A9B4C0;
  font-weight: 600;
}
.pru-chip .v {
  font-size: 0.92rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: #F4F0E6;
}
.pru-chip .up { color: #3DDC97; font-size: 0.78rem; font-weight: 600; }
.pru-chip .dn { color: #FF8A80; font-size: 0.78rem; font-weight: 600; }
.pru-chip .na { color: #8A96A3; font-size: 0.78rem; }

.pru-lede {
  color: var(--ink-soft);
  font-size: 1.02rem;
  margin: 0 0 1rem 0;
  max-width: 46rem;
}
.pru-lede strong { color: var(--navy-900); }

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(270px, 1fr));
  gap: 0.9rem;
  margin: 0.4rem 0 1rem 0;
}
.kpi-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 1rem 1.05rem 0.95rem;
  box-shadow: 0 8px 24px rgba(11,28,44,0.05);
}
.kpi-card .row1 {
  display: flex; justify-content: space-between; align-items: baseline; gap: 0.5rem;
}
.kpi-card .sym {
  font-weight: 700; letter-spacing: 0.06em; color: var(--navy-900); font-size: 0.82rem;
}
.kpi-card .sec {
  font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em;
}
.kpi-card .cname {
  color: var(--muted); font-size: 0.82rem; margin: 0.15rem 0 0.45rem;
}
.kpi-card .px {
  font-family: Fraunces, Georgia, serif;
  font-size: 1.7rem;
  font-weight: 700;
  color: var(--navy-900);
  line-height: 1;
}
.kpi-card .chg { font-size: 0.88rem; font-weight: 600; margin-left: 0.45rem; }
.chg-up { color: var(--up); }
.chg-dn { color: var(--down); }
.kpi-metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.45rem;
  margin: 0.85rem 0 0.7rem;
}
.kpi-metrics div {
  background: #F7F3EA;
  border-radius: 8px;
  padding: 0.4rem 0.35rem;
  text-align: center;
}
.kpi-metrics span {
  display: block; font-size: 0.64rem; color: var(--muted);
  letter-spacing: 0.06em; text-transform: uppercase; font-weight: 600;
}
.kpi-metrics b {
  display: block; font-size: 0.86rem; color: var(--navy-900); margin-top: 0.12rem;
  font-variant-numeric: tabular-nums;
}
.range-track {
  position: relative; height: 7px; background: #E6DFD1; border-radius: 99px; margin: 0.45rem 0 0.3rem;
}
.range-fill {
  position: absolute; left: 0; top: 0; bottom: 0;
  background: linear-gradient(90deg, #1A3650, #D4AF67);
  border-radius: 99px;
}
.range-marker {
  position: absolute; top: 50%; width: 11px; height: 11px; background: var(--navy-900);
  border: 2px solid #fff; border-radius: 50%; transform: translate(-50%, -50%);
  box-shadow: 0 0 0 1px rgba(196,163,90,0.7);
}
.range-labels {
  display: flex; justify-content: space-between; color: var(--muted); font-size: 0.72rem;
}
.tgt { margin-top: 0.45rem; font-size: 0.78rem; color: var(--ink-soft); }

.pipe {
  display: flex; flex-wrap: wrap; gap: 0.4rem; align-items: stretch;
  margin: 0.35rem 0 0.85rem;
}
.pipe-step {
  flex: 1 1 110px;
  min-width: 108px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.55rem 0.6rem 0.5rem;
  position: relative;
}
.pipe-step .n {
  font-size: 0.62rem; letter-spacing: 0.12em; color: var(--muted); font-weight: 700;
}
.pipe-step .t {
  font-size: 0.8rem; font-weight: 600; color: var(--navy-900); margin-top: 0.12rem;
}
.pipe-step.done {
  border-color: rgba(31,138,91,0.35);
  background: #F3FAF6;
}
.pipe-step.done .n { color: var(--up); }
.pipe-step.active {
  border-color: var(--gold-500);
  background: #FFF8EA;
  box-shadow: 0 0 0 3px rgba(196,163,90,0.16);
}
.pipe-step.active .n { color: var(--gold-600); }
.pipe-step.active .t::after {
  content: "";
  display: inline-block;
  width: 7px; height: 7px; margin-left: 6px;
  border-radius: 50%; background: var(--gold-500);
  animation: pulse 1.2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 0.35; transform: scale(0.85); }
  50% { opacity: 1; transform: scale(1.15); }
}

.note-mast {
  background: var(--navy-900);
  color: #F4F0E6;
  border-radius: 16px 16px 0 0;
  padding: 1rem 1.2rem;
  display: flex; justify-content: space-between; gap: 1rem; align-items: flex-end;
}
.note-mast .kicker {
  font-size: 0.68rem; letter-spacing: 0.16em; text-transform: uppercase; color: var(--gold-400); font-weight: 700;
}
.note-mast h3 {
  font-family: Fraunces, Georgia, serif; font-size: 1.25rem; margin: 0.2rem 0 0; font-weight: 700; color: #fff;
}
.note-mast .meta { font-size: 0.78rem; color: #C5CDD6; text-align: right; }
.note-body-anchor { display: none; }
div[data-testid="stVerticalBlock"]:has(.note-body-anchor) .stMarkdown p,
div[data-testid="stVerticalBlock"]:has(.note-body-anchor) .stMarkdown li {
  font-family: "Source Serif 4", Georgia, serif;
  font-size: 1.05rem;
  line-height: 1.65;
  color: #243040;
}

.wp-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 0.45rem;
  margin: 0.4rem 0 0.8rem;
}
.wp-pill {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 0.55rem 0.6rem;
  text-align: center;
}
.wp-pill .l { font-size: 0.72rem; color: var(--muted); font-weight: 600; }
.wp-pill .s { font-size: 0.82rem; font-weight: 700; margin-top: 0.15rem; }
.wp-ok { color: var(--up); }
.wp-thin { color: #B45309; }

.symbol-row { display: flex; flex-wrap: wrap; gap: 0.35rem; margin: 0.25rem 0 0.6rem; }
.sym-tag {
  background: #EFE7D4;
  color: var(--navy-900);
  border-radius: 999px;
  padding: 0.18rem 0.65rem;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.query-bar {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 0.85rem 1rem;
  margin: 0.4rem 0 1rem;
}
.query-bar .qlabel {
  font-size: 0.68rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted); font-weight: 700;
}
.query-bar .qtext {
  font-family: "Source Serif 4", Georgia, serif;
  font-size: 1.12rem;
  color: var(--navy-900);
  margin-top: 0.2rem;
}

.hero-card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 1rem 1.05rem;
  height: 100%;
}
.hero-card h4 {
  font-family: Fraunces, Georgia, serif;
  margin: 0 0 0.35rem;
  color: var(--navy-900);
}
.hero-card p { color: var(--ink-soft); font-size: 0.9rem; margin: 0; }

.side-logo { display: flex; align-items: center; gap: 0.7rem; margin: 0.15rem 0 0.85rem; }
.side-logo .name { font-family: Fraunces, Georgia, serif; font-size: 1.25rem; color: #F7F1E4 !important; }
.side-logo .sub { font-size: 0.65rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--gold-400) !important; }

.status-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.35rem; margin: 0.4rem 0 0.7rem; }
.status-cell {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 9px;
  padding: 0.4rem 0.5rem;
  font-size: 0.75rem;
}
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 0.35rem; }
.dot-on { background: #3DDC97; box-shadow: 0 0 0 3px rgba(61,220,151,0.18); }
.dot-off { background: #6B7785; }
.dot-opt { background: #D4AF67; }

.desk-foot {
  margin-top: 2rem;
  padding-top: 0.9rem;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 0.8rem;
  line-height: 1.5;
}

@media (max-width: 900px) {
  .pru-masthead { flex-direction: column; align-items: flex-start; }
  .pru-tape { justify-content: flex-start; }
  .kpi-metrics { grid-template-columns: repeat(2, 1fr); }
}
"""


def _esc(v: Any) -> str:
    return html.escape("" if v is None else str(v))


def _fmt_chg(chg: Optional[float]) -> str:
    if chg is None:
        return '<span class="na">—</span>'
    cls = "up" if chg >= 0 else "dn"
    sign = "+" if chg >= 0 else ""
    return f'<span class="{cls}">{sign}{chg:.2f}%</span>'


def tape_html(items: list[dict[str, Any]]) -> str:
    chips = []
    for it in items:
        last = it.get("last")
        last_s = f"{last:,.2f}" if isinstance(last, (int, float)) else "—"
        chips.append(
            "<div class='pru-chip'>"
            f"<div class='k'>{_esc(it.get('label'))}</div>"
            f"<div class='v'>{_esc(last_s)} {_fmt_chg(it.get('chg'))}</div>"
            "</div>"
        )
    return f"<div class='pru-tape'>{''.join(chips)}</div>"


def masthead_html(tape_items: list[dict[str, Any]] | None = None) -> str:
    tape = tape_html(tape_items or []) if tape_items else ""
    return f"""
    <div class="pru-masthead">
      <div class="pru-brand">
        {LOGO_SVG}
        <div>
          <div class="name">PruInsight</div>
          <div class="sub">Multi-agent research desk</div>
        </div>
      </div>
      {tape}
    </div>
    """


def sidebar_brand_html() -> str:
    return f"""
    <div class="side-logo">
      {LOGO_SVG}
      <div>
        <div class="name">PruInsight</div>
        <div class="sub">Research desk</div>
      </div>
    </div>
    """


def status_grid_html(keys: dict[str, bool], langsmith_on: bool) -> str:
    cells = [
        ("Groq", keys.get("groq"), False),
        ("Tavily", keys.get("tavily"), True),
        ("Serper", keys.get("serper"), True),
        ("DuckDuckGo", keys.get("duckduckgo"), False),
        ("FRED", keys.get("fred"), True),
        ("LangSmith", langsmith_on, True),
    ]
    bits = []
    for label, on, optional in cells:
        if on:
            dot = "dot-on"
        elif optional:
            dot = "dot-opt"
        else:
            dot = "dot-off"
        state = "live" if on else ("optional" if optional else "required")
        bits.append(
            f"<div class='status-cell'><span class='dot {dot}'></span>"
            f"{_esc(label)} · {state}</div>"
        )
    return f"<div class='status-grid'>{''.join(bits)}</div>"


def pipeline_html(
    steps: list[tuple[str, str, str]],
    done: list[str] | None = None,
    active: str | None = None,
) -> str:
    done_set = set(done or [])
    parts = []
    for i, (key, name, _) in enumerate(steps, 1):
        cls = "pipe-step"
        if key in done_set:
            cls += " done"
        elif key == active:
            cls += " active"
        parts.append(
            f"<div class='{cls}'><div class='n'>0{i}</div>"
            f"<div class='t'>{_esc(name)}</div></div>"
        )
    return f"<div class='pipe'>{''.join(parts)}</div>"


def kpi_cards_html(cards: list[dict[str, Any]]) -> str:
    blocks = []
    for c in cards:
        chg = c.get("chg")
        if chg is None:
            chg_html = ""
        else:
            cls = "chg-up" if chg >= 0 else "chg-dn"
            sign = "+" if chg >= 0 else ""
            chg_html = f"<span class='chg {cls}'>{sign}{chg:.2f}%</span>"
        pos = c.get("range_pos")
        range_html = ""
        if isinstance(pos, (int, float)):
            pct = min(max(pos, 0.0), 1.0) * 100.0
            range_html = f"""
              <div class="range-track">
                <div class="range-fill" style="width:{pct:.1f}%"></div>
                <div class="range-marker" style="left:{pct:.1f}%"></div>
              </div>
              <div class="range-labels">
                <span>52w low {_esc(c.get('low_s'))}</span>
                <span>52w high {_esc(c.get('high_s'))}</span>
              </div>
            """
        tgt = c.get("tgt_s")
        tgt_html = f"<div class='tgt'>Street target · {_esc(tgt)}</div>" if tgt else ""
        metrics = "".join(
            f"<div><span>{_esc(k)}</span><b>{_esc(v)}</b></div>"
            for k, v in c.get("metrics", [])
        )
        blocks.append(
            f"""
            <div class="kpi-card">
              <div class="row1">
                <div class="sym">{_esc(c.get('symbol'))}</div>
                <div class="sec">{_esc(c.get('sector'))}</div>
              </div>
              <div class="cname">{_esc(c.get('name'))}</div>
              <div class="px">{_esc(c.get('price_s'))}{chg_html}</div>
              <div class="kpi-metrics">{metrics}</div>
              {range_html}
              {tgt_html}
            </div>
            """
        )
    return f"<div class='kpi-grid'>{''.join(blocks)}</div>"


def workpaper_pills_html(items: list[tuple[str, bool]]) -> str:
    bits = []
    for label, ok in items:
        cls = "wp-ok" if ok else "wp-thin"
        state = "Ready" if ok else "Thin"
        bits.append(
            f"<div class='wp-pill'><div class='l'>{_esc(label)}</div>"
            f"<div class='s {cls}'>{state}</div></div>"
        )
    return f"<div class='wp-grid'>{''.join(bits)}</div>"


def query_bar_html(query: str, symbols: list[str], when: str) -> str:
    tags = "".join(f"<span class='sym-tag'>{_esc(s)}</span>" for s in symbols) or (
        "<span class='sym-tag'>No symbols</span>"
    )
    return f"""
    <div class="query-bar">
      <div class="qlabel">Active brief · { _esc(when) }</div>
      <div class="qtext">{_esc(query)}</div>
      <div class="symbol-row">{tags}</div>
    </div>
    """


def note_masthead_html(title: str, meta_right: str) -> str:
    return f"""
    <div class="note-mast">
      <div>
        <div class="kicker">PruInsight research note</div>
        <h3>{_esc(title)}</h3>
      </div>
      <div class="meta">{_esc(meta_right)}</div>
    </div>
    """

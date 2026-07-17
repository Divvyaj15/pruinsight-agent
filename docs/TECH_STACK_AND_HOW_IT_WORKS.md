# PruInsight — Tech Stack & How It Works

Complete technical reference for the multi-agent equity research system.  
Use this alongside the quick-start [README.md](./README.md), Docker tutorial [DOCKER_LEARNING.md](./DOCKER_LEARNING.md), and (private) [MY_PROJECT_GUIDE.md](./MY_PROJECT_GUIDE.md).

> **Educational demo.** Not investment advice. Not an official ICICI Prudential AMC product.

---

## Table of contents

1. [What the system does](#1-what-the-system-does)
2. [High-level architecture](#2-high-level-architecture)
3. [Full tech stack](#3-full-tech-stack)
4. [Repository layout](#4-repository-layout)
5. [Shared state (`AgentState`)](#5-shared-state-agentstate)
6. [LangGraph pipeline (how agents connect)](#6-langgraph-pipeline-how-agents-connect)
7. [Each agent explained](#7-each-agent-explained)
8. [Tools catalog](#8-tools-catalog)
9. [Search cascade (Tavily → Serper → DuckDuckGo)](#9-search-cascade-tavily--serper--duckduckgo)
10. [Filings RAG (PDF + BM25)](#10-filings-rag-pdf--bm25)
11. [AMFI mutual fund data](#11-amfi-mutual-fund-data)
12. [Macro (RBI + FRED + Yahoo)](#12-macro-rbi--fred--yahoo)
13. [LLM layer (Groq)](#13-llm-layer-groq)
14. [Report export (Markdown + PDF + data sources)](#14-report-export-markdown--pdf--data-sources)
15. [Frontends: CLI and Streamlit](#15-frontends-cli-and-streamlit)
16. [Configuration and secrets](#16-configuration-and-secrets)
17. [Docker packaging](#17-docker-packaging)
18. [End-to-end request lifecycle](#18-end-to-end-request-lifecycle)
19. [Data flow diagram](#19-data-flow-diagram)
20. [Roadmap and design choices](#20-roadmap-and-design-choices)
21. [Limitations and disclaimers](#21-limitations-and-disclaimers)

---

## 1. What the system does

**PruInsight** turns a free-text research question (and optional NSE symbols like `HDFCBANK`) into a structured **mutual-fund desk style research note**.

It does this with **multiple specialized AI agents** that run **in sequence**, each writing its findings into shared state. Agents use **tools** to pull real data (search, Yahoo Finance, AMFI, PDFs, macro series) instead of inventing numbers.

**Typical output sections**

- Executive summary  
- Market & news context  
- Macro & policy backdrop  
- Primary sources & filings  
- Fundamentals snapshot  
- Mutual fund context (AMFI / factsheets)  
- Risk view  
- MF perspective (horizon, sizing, monitoring)  
- Key takeaways + disclaimer  
- **Data sources** appendix (auto-appended)

---

## 2. High-level architecture

```
┌─────────────────────────────────────────────────────────────┐
│  ENTRYPOINTS                                                 │
│  • CLI: main.py                                              │
│  • UI:  streamlit_app.py                                     │
│  • Docker: streamlit on :8501                                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  runner.run_research(query, symbols)                         │
│  • builds graph  • invokes  • appends Data sources           │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  LangGraph StateGraph                                        │
│                                                              │
│  researcher → filings → transcripts → fundamentals           │
│       → mf_context → macro → risk → synthesizer → END        │
│                                                              │
│  Shared: AgentState (TypedDict)                              │
└──────────┬───────────────────────────────────────────────────┘
           │
           │  tools call external systems
           ▼
┌──────────────┐  ┌────────────┐  ┌─────────┐  ┌──────────┐
│ Search       │  │ yfinance   │  │ AMFI    │  │ FRED     │
│ Tavily/Serper│  │ NSE quotes │  │ NAVAll  │  │ optional │
│ /DuckDuckGo  │  │ financials │  │ schemes │  │          │
└──────────────┘  └────────────┘  └─────────┘  └──────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│  PDF RAG (pypdf + BM25)                                      │
│  • company filings store                                     │
│  • fund factsheet store                                      │
└─────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│  Groq LLM (langchain-groq)                                   │
│  Interprets tool output; writes agent briefs + final note    │
└─────────────────────────────────────────────────────────────┘
```

**Core idea:** orchestration is **LangGraph**; intelligence is **Groq LLMs**; truthfulness is improved by **tools + RAG**.

---

## 3. Full tech stack

### 3.1 Language & packaging

| Piece | Role |
|-------|------|
| **Python 3.11+** | Runtime |
| **venv / Docker image** | Isolated dependencies |
| **`pruinsight/` package** | Importable application code |
| **`requirements.txt`** | Declared Python deps |
| **`python-dotenv`** | Load `.env` secrets locally |

### 3.2 AI / agent framework

| Package | Role |
|---------|------|
| **langgraph** | Multi-agent graph: nodes, edges, `compile()`, `invoke()` |
| **langchain** | Ecosystem glue |
| **langchain-core** | Messages (`SystemMessage`, `HumanMessage`, `ToolMessage`), `@tool` |
| **langchain-groq** | Chat model client for Groq-hosted LLMs |
| **Groq API** | Hosted inference (default model: Llama scout instruct family) |

### 3.3 Search & discovery

| Provider | Package / access | When used |
|----------|------------------|-----------|
| **Tavily** | `tavily-python` | Primary agent-friendly web/news search |
| **Serper** | HTTPS API + `requests` | Optional Google SERP fallback (`SERPER_API_KEY`) |
| **DuckDuckGo** | `ddgs` | Free last-resort fallback (no API key) |

Cascade implemented in `pruinsight/tools/search_providers.py`.

### 3.4 Market & fund data

| Source | Access | Data |
|--------|--------|------|
| **Yahoo Finance** | `yfinance` | NSE `SYMBOL.NS` quotes, financials, history, news, analyst fields, indices |
| **AMFI India** | HTTP download of `NAVAll.txt` | Scheme codes, names, latest NAV, category banners, AMC |
| **FRED** | REST API | US rates, curve, VIX, oil, USD/INR series (optional key) |
| **RBI** | Public site + multi-provider search | Policy/MPC narrative (not full DBIE table scrape) |

### 3.5 Documents & RAG

| Piece | Package | Role |
|-------|---------|------|
| PDF download | `requests` | HTTP GET of filing/factsheet PDFs |
| PDF text extract | `pypdf` | Page text extraction |
| Chunk store | custom `FilingsStore` | In-memory corpus + metadata |
| Retrieval | `rank-bm25` (BM25Okapi) | Keyword RAG without embeddings/vector DB |

Three separate BM25 stores:

- company filings → `get_filings_store()`  
- fund factsheets → `get_factsheet_store()`  
- earnings transcripts → `get_transcript_store()`  

### 3.6 UI & export

| Piece | Role |
|-------|------|
| **Streamlit** | Web UI: form, examples, intermediate tabs, downloads |
| **CLI (`main.py`)** | Argparse entry; optional `--pdf` |
| **fpdf2** | Render research note to PDF |
| **`report_export.py`** | Data-sources appendix + PDF helpers |

### 3.7 Ops / deploy

| Piece | Role |
|-------|------|
| **Dockerfile** | Image recipe (Python slim + deps + Streamlit) |
| **docker-compose.yml** | Ports, `env_file`, one-command run |
| **.dockerignore** | Keep secrets and junk out of the image |
| **.streamlit/config.toml** | Bind `0.0.0.0:8501` for containers |

---

## 4. Repository layout

```
pruinsight-agent/
├── main.py                      # CLI entry
├── streamlit_app.py             # Streamlit UI
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env                         # secrets (gitignored)
├── .streamlit/config.toml
├── README.md                    # setup & usage
├── TECH_STACK_AND_HOW_IT_WORKS.md  # this file
├── DOCKER_LEARNING.md           # Docker tutorial
├── MY_PROJECT_GUIDE.md          # private notes (gitignored)
│
└── pruinsight/                  # main Python package
    ├── state.py                 # AgentState
    ├── llm.py                   # get_llm() → ChatGroq
    ├── graph.py                 # StateGraph wiring
    ├── runner.py                # run_research() shared by CLI/UI
    ├── report_export.py         # sources appendix + PDF/MD
    │
    ├── rag/
    │   └── store.py             # BM25 FilingsStore + factories
    │
    ├── tools/
    │   ├── search_providers.py  # multi-provider search cascade
    │   ├── market_tools.py      # web/news/stock/financials/peers
    │   ├── filings_tools.py     # filing search, PDF ingest, RAG
    │   ├── amfi_tools.py        # AMFI NAV + factsheet tools
    │   └── macro_tools.py       # India/global macro + RBI
    │
    └── agents/
        ├── tool_loop.py         # multi-round LLM tool calling
        ├── researcher.py
        ├── filings.py
        ├── fundamentals.py
        ├── mf_context.py
        ├── macro.py
        ├── risk.py
        └── synthesizer.py
```

---

## 5. Shared state (`AgentState`)

Defined in `pruinsight/state.py` as a `TypedDict` passed through every node.

| Field | Written by | Meaning |
|-------|------------|---------|
| `query` | User / runner | Research question |
| `symbols` | User / fundamentals | NSE tickers e.g. `["HDFCBANK"]` |
| `market_research` | researcher | News / sector narrative |
| `filings_context` | filings | Primary-source PDF brief |
| `transcripts_context` | transcripts | Earnings call / management brief |
| `fundamentals` | fundamentals | Valuation / quality brief |
| `mf_context` | mf_context | AMFI schemes + factsheet brief |
| `macro_context` | macro | RBI + India/global macro brief |
| `risk_assessment` | risk | Risk & monitoring brief |
| `final_report` | synthesizer (+ sources post-process) | Full note |
| `messages` | various | Tool/LLM traces (`Annotated[..., operator.add]` appends) |

LangGraph merges partial dict returns from each node into the full state.

---

## 6. LangGraph pipeline (how agents connect)

File: `pruinsight/graph.py`

```
START
  → researcher
  → filings
  → transcripts
  → fundamentals
  → mf_context
  → macro
  → risk
  → synthesizer
  → END
```

**Pattern:** sequential hand-off (not a free-for-all multi-agent chat).  
Each node is a pure function: `(state) → partial state update`.

```python
workflow = StateGraph(AgentState)
workflow.add_node("researcher", researcher_node)
# ... more nodes ...
workflow.set_entry_point("researcher")
workflow.add_edge("researcher", "filings")
# ... chain edges ...
workflow.add_edge("synthesizer", END)
app = workflow.compile()
```

**Why sequential?**  
Clear debugging, inspectable intermediate tabs in Streamlit, and predictable tool costs for a learning/demo system.

---

## 7. Each agent explained

### 7.1 Market Researcher (`agents/researcher.py`)

- **Job:** Qualitative market narrative — headlines, sector, catalysts.  
- **Tools (via `tool_loop`):** `web_search`, `news_search`, `get_company_news`, `get_index_snapshot`  
- **Writes:** `market_research`  
- **Mechanism:** LLM bound to tools, up to 2 tool-call rounds, then final brief.

### 7.2 Filings Analyst (`agents/filings.py`)

- **Job:** Primary sources from company/exchange PDFs.  
- **Mechanism (deterministic pipeline + LLM summary):**  
  1. Multi-provider search for AR / results / IR PDFs  
  2. Download + `pypdf` extract (page cap)  
  3. Chunk into BM25 store  
  4. Retrieve excerpts for several queries  
  5. LLM writes `filings_context`  
- **Tools module:** `tools/filings_tools.py`  
- **Store cleared each run** so Streamlit sessions don’t mix issuers.

### 7.3 Transcripts Analyst (`agents/transcripts.py`)

- **Job:** Management tone, guidance, Q&A themes from earnings calls.  
- **Mechanism:** multi-search → ingest PDF/HTML → BM25 transcript store → RAG → LLM brief.  
- **Tools module:** `tools/transcripts_tools.py`  
- **Writes:** `transcripts_context`  
- **Caveat:** paywalls / JS-only pages common.

### 7.4 Fundamentals Analyst (`agents/fundamentals.py`)

- **Job:** Quantitative company view (Screener-style).  
- **Mechanism:** deterministic `programmatic_deep_fundamentals()` pack then LLM interpretation.  
- **Tools module:** `tools/deep_fundamentals.py` (ratios, growth, quarterly, holders, default peers).  
- **Reads:** market research + filings + transcripts  
- **Writes:** `fundamentals`  
- **Extra:** symbol alias map (e.g. “HDFC Bank” → `HDFCBANK`).

### 7.5 MF Context (`agents/mf_context.py`)

- **Job:** Mutual-fund desk lens.  
- **Data:** AMFI `NAVAll.txt` + optional factsheet PDF RAG  
- **Mechanism:** `programmatic_mf_brief()` then LLM synthesis  
- **Writes:** `mf_context`

### 7.6 Macro Analyst (`agents/macro.py`)

- **Job:** Rates / FX / oil / RBI policy regime.  
- **Data:** India market proxies (yfinance), multi-provider RBI search, FRED or Yahoo global  
- **Writes:** `macro_context`

### 7.7 Risk Assessor (`agents/risk.py`)

- **Job:** Downside, thesis kills, portfolio construction risks.  
- **Tools (optional):** `get_price_history`, `get_index_snapshot`  
- **Reads:** all prior briefs (incl. transcripts)  
- **Writes:** `risk_assessment`

### 7.8 Report Synthesizer (`agents/synthesizer.py`)

- **Job:** Merge everything into one institutional note.  
- **Tools:** none  
- **Writes:** `final_report`  
- **Always** ensures a disclaimer is present.

### Shared tool loop (`agents/tool_loop.py`)

Used by agents that need multi-round tool calling:

1. Bind tools to LLM  
2. Invoke; if `tool_calls`, execute via registry / invoke  
3. Append `ToolMessage`s and continue (max rounds)  
4. Final synthesis if needed  

---

## 8. Tools catalog

### Search / news / company headlines

| Tool | Module | Backend |
|------|--------|---------|
| `web_search` | market_tools | Search cascade |
| `news_search` | market_tools | Search cascade (news mode) |
| `get_company_news` | market_tools | yfinance ticker news |

### NSE fundamentals

| Tool | Backend |
|------|---------|
| `get_stock_data` | yfinance `.NS` info |
| `get_financials` | annual statements |
| `get_screener_style_snapshot` | deep pack: ratios + quarterly + holders |
| `get_key_ratios_growth` | valuation, margins, growth, FCF |
| `get_quarterly_financials` | quarterly statements |
| `get_shareholding_overview` | holders (best-effort) |
| `get_default_peer_set` | built-in large-cap peers + metrics |
| `get_price_history` | history, return, vol |
| `get_analyst_view` | targets / recs (often sparse) |
| `get_peer_snapshot` | multi-symbol compare |
| `get_index_snapshot` | NIFTY, BANKNIFTY, INDIAVIX, SENSEX, USDINR |

### Filings RAG

| Tool | Role |
|------|------|
| `search_company_filings` | Find PDF URLs |
| `ingest_filing_pdf` | Download + chunk |
| `query_filings_rag` | BM25 retrieve |
| `list_ingested_filings` | Store summary |

### Earnings transcripts

| Tool | Role |
|------|------|
| `search_earnings_transcripts` | Find concall / earnings transcripts |
| `ingest_transcript_document` | PDF or HTML → transcript store |
| `query_transcripts_rag` | BM25 retrieve guidance / Q&A |
| `list_ingested_transcripts` | Store summary |

### AMFI + factsheets

| Tool | Role |
|------|------|
| `search_amfi_schemes` | Keyword search NAV universe |
| `get_amfi_nav` | NAV by code/name |
| `list_amfi_categories` | Category banners |
| `search_related_equity_funds` | Theme → equity schemes |
| `search_fund_factsheet` | Find AMC PDFs |
| `ingest_fund_factsheet_pdf` | Factsheet RAG ingest |
| `query_factsheet_rag` | Retrieve factsheet chunks |

### Macro

| Tool | Role |
|------|------|
| `get_india_market_macro` | Nifty, Sensex, India VIX, USDINR |
| `get_global_macro_snapshot` | FRED or Yahoo globals |
| `get_fred_series` | Single FRED series |
| `list_fred_presets` | Common series IDs |
| `get_rbi_policy_context` | RBI/MPC search |
| `get_macro_dashboard` | Combined pack |

---

## 9. Search cascade (Tavily → Serper → DuckDuckGo)

File: `pruinsight/tools/search_providers.py`

```
multi_search(query, mode="web"|"news")
    1. Try Tavily     if TAVILY_API_KEY set
    2. Try Serper     if SERPER_API_KEY set
    3. Try DuckDuckGo via ddgs package (no key)
    Return first non-empty hit list + provider_used
```

**Used by:** researcher web/news, filings discovery, factsheet discovery, RBI policy search.

**Why:** resilience to rate limits, outages, and missing keys; still works offline-from-Tavily with free DDG.

Results are labeled with `provider used` so the final report / tool dumps stay auditable.

---

## 10. Filings RAG (PDF + BM25)

```
Search URLs (cascade)
    → download PDF (requests, browser-like headers)
    → pypdf extract (first ~N pages)
    → chunk (~1200 chars, overlap)
    → FilingsStore + BM25Okapi index
    → query(question) → top-k chunks
    → LLM filings brief
```

**Why BM25 instead of embeddings?**

- No embedding API cost  
- No large local embedding model  
- Enough for keyword-heavy financial PDFs in a demo  

**Limits:** scanned/image PDFs yield little text; exchange sites may block bots; page caps mean partial annual reports.

---

## 11. AMFI mutual fund data

- Download: `https://portal.amfiindia.com/spages/NAVAll.txt`  
- Parse scheme rows: code, ISINs, name, NAV, date, category, AMC  
- In-process cache (~1 hour) to avoid re-downloading every tool call  
- Factsheets: multi-provider search → PDF → separate BM25 store  

Gives the MF desk real scheme names and NAVs (e.g. ICICI Prudential Large Cap Direct Growth).

---

## 12. Macro (RBI + FRED + Yahoo)

| Layer | Source | Content |
|-------|--------|---------|
| India market | yfinance | Nifty, Sensex, India VIX, USD/INR levels & recent moves |
| India policy | multi-search | RBI MPC / repo / inflation narrative (prefer rbi.org.in) |
| Global | FRED if key | Fed funds, 10Y, 2Y, curve, VIX, WTI, DEXINUS, … |
| Global fallback | yfinance | ^TNX, ^VIX, CL=F, GC=F |

**DBIE** (`dbie.rbi.org.in`) is documented as the official statistical warehouse; this demo does **not** scrape full DBIE tables.

---

## 13. LLM layer (Groq)

File: `pruinsight/llm.py`

```python
ChatGroq(
    model="meta-llama/llama-4-scout-17b-16e-instruct",  # default
    temperature=...,
    api_key=os.getenv("GROQ_API_KEY"),
)
```

- Used by every agent for reasoning and writing.  
- Tools ground the LLM in retrieved/fetched data.  
- Prompts forbid buy/sell recommendations and push institutional tone.

**Docker note:** `GROQ_API_KEY` is injected at **container run** via Compose `env_file: .env`, not baked into the image.

---

## 14. Report export (Markdown + PDF + data sources)

File: `pruinsight/report_export.py`

After the graph finishes, `runner.enrich_result_with_sources()`:

1. Takes `final_report` from synthesizer  
2. Appends a **Data sources** section listing:  
   - Groq, search cascade, yfinance, FRED, RBI, AMFI  
   - PDFs ingested this run (company filings + factsheets with URLs)  
3. Streamlit / CLI can export:  
   - **Markdown** (raw report string)  
   - **PDF** via fpdf2 (Unicode font when available: Arial on Windows, DejaVu in Docker)

CLI:

```bash
python main.py "..." -s HDFCBANK --pdf note.pdf
```

---

## 15. Frontends: CLI and Streamlit

### CLI (`main.py`)

```bash
python main.py "Latest insights on HDFC Bank" -s HDFCBANK -v
python main.py "..." -s TCS INFY --pdf out.pdf
```

| Flag | Purpose |
|------|---------|
| query | Research question |
| `-s` / `--symbols` | NSE tickers |
| `-v` / `--verbose` | Print each agent intermediate |
| `--pdf PATH` | Save PDF |

### Streamlit (`streamlit_app.py`)

- Query + symbols form  
- Example presets  
- Sidebar: keys status, pipeline, tools  
- Tabs: Market, Filings, Fundamentals, MF/AMFI, Macro, Risk, Pipeline  
- Final note + data sources expander  
- Download **.md** and **.pdf**

Both call the same `pruinsight.runner.run_research()`.

---

## 16. Configuration and secrets

### `.env` (project root, gitignored)

```env
# Required for LLM
GROQ_API_KEY=...

# Preferred primary search
TAVILY_API_KEY=...

# Optional Google SERP fallback
# SERPER_API_KEY=...

# Optional official US macro series
# FRED_API_KEY=...
```

### What is required?

| Capability | Minimum |
|------------|---------|
| LLM agents | `GROQ_API_KEY` |
| Web search | Tavily **or** Serper **or** installed `ddgs` |
| Best quality search | Tavily |
| Richer US rates | FRED key |

### How secrets reach Docker

1. `.dockerignore` excludes `.env` from the image  
2. `docker-compose.yml` has `env_file: .env`  
3. Container process env gets the keys at start  
4. Python `os.getenv(...)` / `load_dotenv()` reads them  

---

## 17. Docker packaging

| File | Purpose |
|------|---------|
| `Dockerfile` | `python:3.11-slim`, install deps, copy app, run Streamlit |
| `docker-compose.yml` | Build, map `8501:8501`, load `.env` |
| `.dockerignore` | Skip `.venv`, `.env`, caches, private notes |

```bash
docker compose up --build          # rebuild after code changes
docker compose up -d --force-recreate   # .env-only changes
docker compose down
```

Browser: **http://localhost:8501**

Full tutorial: [DOCKER_LEARNING.md](./DOCKER_LEARNING.md).

---

## 18. End-to-end request lifecycle

1. User submits query (+ symbols) via CLI or Streamlit.  
2. `run_research` builds graph and `invoke`s initial state.  
3. **Researcher** searches web/news, optional company news & indices → `market_research`.  
4. **Filings** searches PDFs, ingests 1–2 docs, RAG, LLM brief → `filings_context`.  
5. **Transcripts** searches earnings calls, ingests PDF/HTML, RAG → `transcripts_context`.  
6. **Fundamentals** Screener-style deep pack + LLM → `fundamentals`.  
7. **MF context** loads AMFI NAVs, optional factsheet RAG → `mf_context`.  
8. **Macro** builds India + global + RBI pack → `macro_context`.  
9. **Risk** synthesizes risks from all prior text (+ optional vol tools) → `risk_assessment`.  
10. **Synthesizer** writes full IC-style note → `final_report`.  
11. **Runner** appends **Data sources** (providers + ingested PDF/transcript URLs).  
12. UI/CLI displays report; optional Markdown/PDF download.  

Typical wall time: **tens of seconds to a few minutes** (many LLM + network calls).

---

## 19. Data flow diagram

```
User query + symbols
        │
        ▼
┌───────────────┐     search cascade      ┌─────────────┐
│  Researcher   │ ───────────────────────►│ Web / News  │
└───────┬───────┘     yfinance news/idx   └─────────────┘
        │ market_research
        ▼
┌───────────────┐     search + PDF        ┌─────────────┐
│  Filings      │ ───────────────────────►│ NSE/BSE PDFs│
└───────┬───────┘     BM25 RAG            └─────────────┘
        │ filings_context
        ▼
┌───────────────┐     yfinance            ┌─────────────┐
│ Fundamentals  │ ───────────────────────►│ NSE metrics │
└───────┬───────┘                         └─────────────┘
        │ fundamentals
        ▼
┌───────────────┐     NAVAll.txt + PDFs   ┌─────────────┐
│  MF Context   │ ───────────────────────►│ AMFI / AMC  │
└───────┬───────┘                         └─────────────┘
        │ mf_context
        ▼
┌───────────────┐     yfinance/FRED/search┌─────────────┐
│  Macro        │ ───────────────────────►│ RBI/Global  │
└───────┬───────┘                         └─────────────┘
        │ macro_context
        ▼
┌───────────────┐
│  Risk         │  (LLM + optional vol tools)
└───────┬───────┘
        │ risk_assessment
        ▼
┌───────────────┐     Groq only
│  Synthesizer  │ ───────────────────────► final_report
└───────┬───────┘
        ▼
  + Data sources appendix
        ▼
  Streamlit / CLI / PDF
```

---

## 20. Roadmap and design choices

### Implemented roadmap

| Step | Capability | Status |
|------|------------|--------|
| 1 | Company filings PDF + BM25 RAG | Done |
| 2 | AMFI + fund factsheets | Done |
| 3 | RBI / FRED macro | Done |
| 4 | Serper / DuckDuckGo search fallback | Done |
| 5 | Screener-style deep India fundamentals | Done |
| 6 | Earnings transcripts | Done |

### Design choices

| Choice | Rationale |
|--------|-----------|
| Sequential agents | Teachable, debuggable, tab-friendly UI |
| Package under `pruinsight/` | Clean imports, scales with more modules |
| Shared `runner.py` | One pipeline for CLI + UI + Docker |
| BM25 RAG | Free, simple, no vector DB ops burden |
| Deterministic filings/AMFI/macro packs | More reliable than pure LLM tool-picking for multi-step data work |
| Search cascade | Resilience when Tavily fails |
| Secrets via env at runtime | Safer Docker images |
| No buy/sell language | Safer educational framing for MF internship context |

---

## 21. Limitations and disclaimers

- **Not investment advice.** Demo / learning only.  
- Market data may be **delayed, incomplete, or wrong**.  
- Yahoo analyst fields are often **sparse for Indian names**.  
- PDF RAG is **partial** (page limits, OCR gaps on scans).  
- RBI **DBIE** full tables are **not** ingested.  
- Search snippets can **misstate** policy rates — verify on official sites.  
- LLMs can still **hallucinate** around tool gaps; intermediate tabs help audit.  
- Views are **not** official ICICI Prudential AMC positions.

---

## Quick command reference

```bash
# Local (use project venv)
pip install -r requirements.txt
python main.py "HDFC Bank for MF desk" -s HDFCBANK -v
streamlit run streamlit_app.py

# Docker
docker compose up --build
# → http://localhost:8501
docker compose down
```

---

*This document describes the system as implemented with: LangGraph multi-agent pipeline, filings + factsheet RAG, AMFI, macro, multi-provider search, Streamlit, PDF export, and Docker deploy.*

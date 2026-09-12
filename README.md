# PruInsight Agent

**PruInsight** is a multi-agent equity research demo built with **LangGraph**, **Groq**, **Tavily**, and **yfinance**.

It produces a structured mutual-fund-style research note for Indian (NSE) stocks — news context, fundamentals, risks, and a final synthesized report. Use it from the **command line** or a **Streamlit web UI**.

> **Educational / demo only.** Not investment advice and not an official ICICI Prudential AMC product.

### Documentation map

| Doc | What’s inside |
|-----|----------------|
| **[README.md](./README.md)** (this file) | Setup, run, usage, troubleshooting |
| **[TECH_STACK_AND_HOW_IT_WORKS.md](./TECH_STACK_AND_HOW_IT_WORKS.md)** | **Full tech stack, architecture, every agent/tool, data flow** |
| **[DOCKER_LEARNING.md](./DOCKER_LEARNING.md)** | Step-by-step Docker tutorial |
| **[LANGSMITH_STUDIO_SETUP.md](./LANGSMITH_STUDIO_SETUP.md)** | LangSmith Studio / `langgraph dev` |
| `MY_PROJECT_GUIDE.md` | Private notes (gitignored, local only) |

---

## What it does

You give PruInsight a research question (and optionally NSE symbols). **Eight specialized agents** run in sequence:

```
Your query
    │
    ▼
1. Market Researcher   → web/news, headlines, indices
2. Filings Analyst     → SEBI/BSE/NSE/IR PDFs + BM25 RAG
3. Transcripts Analyst → earnings call transcripts + BM25 RAG
4. Fundamentals        → Screener-style ratios, quarterly, peers
5. MF Context (AMFI)   → NAVs + fund factsheet RAG
6. Macro Analyst       → RBI + India/global macro (FRED optional)
7. Risk Assessor       → downside / portfolio risks
8. Report Synthesizer  → final MF-desk note + disclaimer
```

| Agent | What it contributes | Tools used |
|-------|---------------------|------------|
| **Market Researcher** | Headlines, catalysts, sector story | search cascade, company news, indices |
| **Filings Analyst** | Primary-source PDF excerpts | filings search/ingest/RAG |
| **Transcripts Analyst** | Management guidance, Q&A themes | transcript search/ingest/RAG |
| **Fundamentals Analyst** | Screener-style deep metrics | deep_fundamentals pack |
| **MF Context** | AMFI schemes/NAVs + factsheets | AMFI + factsheet tools |
| **Macro Analyst** | RBI/MPC + India/global levels | macro dashboard, FRED/Yahoo |
| **Risk Assessor** | Risks, monitoring checklist | price history, indices (+ prior text) |
| **Report Synthesizer** | Final PruInsight note | LLM only |

**Typical output sections**

- Executive summary  
- Market & news context  
- Fundamentals snapshot  
- Risk view  
- Mutual fund perspective (horizon, sizing, monitoring)  
- Key takeaways  
- Disclaimer  

---

## Research tools (built in)

| Tool | Source | What you get |
|------|--------|----------------|
| `web_search` | **Tavily** | Broad web research (filings mentions, analysis, thematic) |
| `news_search` | **Tavily** (news topic) | Recent news-biased results |
| `get_company_news` | **Yahoo Finance** via yfinance | Company headline feed for `SYMBOL.NS` |
| `search_company_filings` | **Tavily** (BSE/NSE/SEBI-biased) | Annual reports, results, IR / exchange docs |
| `ingest_filing_pdf` | **HTTP + pypdf** | Download PDF, extract text, chunk into RAG store |
| `query_filings_rag` | **BM25** (`rank-bm25`) | Relevant excerpts from ingested filings |
| `list_ingested_filings` | In-memory store | What was loaded this run |
| `search_amfi_schemes` | **AMFI NAVAll.txt** | Scheme search + latest NAV |
| `get_amfi_nav` | **AMFI** | NAV by scheme code/name |
| `list_amfi_categories` | **AMFI** | Category banners |
| `search_related_equity_funds` | **AMFI** | Theme → equity schemes |
| `search_fund_factsheet` | **Tavily** | AMC factsheet PDF discovery |
| `ingest_fund_factsheet_pdf` | **pypdf** | Factsheet → factsheet RAG store |
| `query_factsheet_rag` | **BM25** | Factsheet excerpts |
| `get_stock_data` | **yfinance** NSE | Price, valuation multiples, margins, ROE, targets |
| `get_financials` | **yfinance** | Annual income / balance sheet / cash flow highlights |
| `get_price_history` | **yfinance** | Period return, high/low, approx. annualized vol |
| `get_analyst_view` | **yfinance** | Mean/high/low targets, recommendation summary |
| `get_index_snapshot` | **yfinance** | NIFTY, Bank Nifty, India VIX, Sensex, USD/INR |
| `get_peer_snapshot` | **yfinance** | Side-by-side P/E, P/B, ROE, mkt cap for peers |

Market tools: `pruinsight/tools/market_tools.py`  
Filings + RAG: `pruinsight/tools/filings_tools.py`, `pruinsight/rag/store.py`  
Agent tool loop: `pruinsight/agents/tool_loop.py`

### Filings + RAG (step 1 enhancement)

How it works each run:

1. **Search** — Tavily looks for annual reports, quarterly results, investor decks; ranks BSE/NSE/SEBI/IR links higher.  
2. **Ingest** — downloads up to 2 PDF URLs, extracts text with **pypdf** (first ~40 pages).  
3. **Chunk** — ~1200-character chunks with overlap.  
4. **Retrieve** — **BM25** keyword RAG (no paid vector DB / embedding API).  
5. **Brief** — Filings agent writes a primary-source brief; later agents and the synthesizer use it.

**Limits (by design for a demo):** scanned image-only PDFs yield little text; some exchange URLs block bots; page cap means not the full annual report; always verify against official filings for real work.

### AMFI + fund factsheets (step 2 enhancement)

How it works each run:

1. **Download** official AMFI `NAVAll.txt` (cached ~1 hour in process).  
2. **Search** schemes by theme (large cap, banking, flexi cap, query keywords).  
3. **Snapshot** latest NAV + date + category for representative funds.  
4. **Factsheet** — Tavily finds AMC factsheet PDFs → pypdf extract → separate BM25 store.  
5. **MF Context agent** writes a mutual-fund desk brief used by Risk + Synthesizer.

Source file: `https://portal.amfiindia.com/spages/NAVAll.txt`  
Code: `pruinsight/tools/amfi_tools.py`, `pruinsight/agents/mf_context.py`

### Macro — RBI + FRED (step 3 enhancement)

| Piece | Source | Notes |
|-------|--------|--------|
| India market levels | yfinance | Nifty, Sensex, India VIX, USD/INR |
| RBI policy narrative | Tavily → rbi.org.in / media | Repo/MPC/inflation context |
| Global rates/oil/VIX | **FRED** if `FRED_API_KEY` set | Else Yahoo proxies |
| DBIE | https://dbie.rbi.org.in/ | Linked as official warehouse; not full table scrape |

Optional `.env`:

```env
FRED_API_KEY=your_free_fred_key
```

Free key: https://fred.stlouisfed.org/docs/api/api_key.html  

Code: `pruinsight/tools/macro_tools.py`, `pruinsight/agents/macro.py`

### Search fallback cascade (step 4)

All web/news/filing/factsheet/RBI searches go through `pruinsight/tools/search_providers.py`:

```
Tavily (primary, if TAVILY_API_KEY)
    → Serper (optional Google SERP, if SERPER_API_KEY)
        → DuckDuckGo (free, via `ddgs` package — no key)
```

- Results annotate which provider was used.
- `GROQ_API_KEY` remains required for the LLM; search can run without Tavily if DuckDuckGo is installed.

Optional `.env`:

```env
SERPER_API_KEY=your_serper_key   # https://serper.dev/
```

### Screener-style deep fundamentals (step 5)

Without scraping Screener.in (ToS/fragility), fundamentals now use a **yfinance-backed Screener-style pack**:

| Tool | Content |
|------|---------|
| `get_screener_style_snapshot` | One-shot: ratios + quarterly + holders + earnings dates |
| `get_key_ratios_growth` | Valuation, margins, leverage, YoY growth, FCF, 52w range |
| `get_quarterly_financials` | Quarterly income / BS / cash flow tables |
| `get_shareholding_overview` | Major / institutional / MF holders (best-effort) |
| `get_default_peer_set` | Built-in peer lists for common large-caps + metrics |

Code: `pruinsight/tools/deep_fundamentals.py` — fundamentals agent always loads this pack for in-scope symbols.

### Earnings transcripts (step 6)

| Tool | Role |
|------|------|
| `search_earnings_transcripts` | Multi-provider search for concall / earnings transcripts |
| `ingest_transcript_document` | PDF or HTML → text → transcript BM25 store |
| `query_transcripts_rag` | Retrieve management guidance / Q&A excerpts |
| `list_ingested_transcripts` | What was loaded this run |

Pipeline node: **transcripts** (after filings, before fundamentals).  
Code: `pruinsight/tools/transcripts_tools.py`, `pruinsight/agents/transcripts.py`.

**Caveat:** many full transcripts are paywalled or JS-only; the agent reports gaps honestly.

---

## Other tools & sources you can add later

Below is a practical map for **Indian equity / MF research**. Pick by budget, reliability, and legal terms of use.

### Market data & fundamentals

| Source | Good for | Notes |
|--------|----------|--------|
| **yfinance** (already used) | Quotes, history, basic financials | Free, unofficial; can break or rate-limit |
| **NSE / BSE official sites & APIs** | Official prices, corporate actions | Stability varies; respect robots/ToS |
| **`nsepython` / similar wrappers** | India-native quotes, option chain | Community libs; validate carefully |
| **Alpha Vantage** | Global fundamentals & time series | Free tier + key; India coverage uneven |
| **Finnhub** | News, fundamentals, filings metadata | Free tier + key |
| **Polygon.io** | High-quality market data | Paid; strong US, check India |
| **Tiingo** | Clean EOD prices | Key required |
| **Bloomberg / Refinitiv / FactSet** | Institutional gold standard | Expensive; enterprise contracts |
| **CMIE / Ace Equity / Capitaline** | Deep India fundamentals | Common on India buy-side desks |
| **Screener.in** | India ratios, peers, quarterly | Great UX; scrape only if ToS allows |

### News & research text

| Source | Good for | Notes |
|--------|----------|--------|
| **Tavily** (already used) | Agent-friendly web search | Built for LLM apps |
| **Serper / Google Programmable Search** | Google-quality SERP JSON | Key + quota |
| **DuckDuckGo (`ddgs`)** | Free search fallback | No key; quality varies |
| **NewsAPI / GNews** | Headlined news feeds | Key; licensing for prod |
| **Economic Times / BS / Mint / Moneycontrol RSS** | India financial news | RSS or licensed APIs |
| **Company IR / annual reports PDFs** | Primary source quality | Pair with PDF/OCR loaders |
| **SEBI / BSE filings / exchange notices** | Regulatory truth | Best for compliance-grade notes |

### Macro, rates & flows

| Source | Good for | Notes |
|--------|----------|--------|
| **RBI DBIE / bulletins** | Policy rates, liquidity, India macro | Official |
| **MOSPI / MoSPI, Budget docs** | Growth, inflation context | Public stats |
| **FRED (St. Louis Fed)** | Global rates, commodities, USD | Free API key |
| **World Bank / IMF** | Cross-country macro | APIs available |
| **India VIX / Nifty** (already via yfinance) | Risk regime | Good enough for demos |
| **EPFR / Bloomberg fund flows** | MF/FII flow narratives | Commercial |

### Mutual fund–specific

| Source | Good for | Notes |
|--------|----------|--------|
| **AMFI** | Industry AUM, categories | Public data |
| **Value Research / Morningstar India** | Fund holdings, category peers | Licensing for bulk use |
| **MF Central / RTA data** | Operational MF data | Not always agent-friendly |
| **Scheme factsheets & SID/SAI** | Mandate, risks, benchmarks | PDF ingest + RAG |

### Alternative / unstructured

| Source | Good for | Notes |
|--------|----------|--------|
| **Transcripts (earnings calls)** | Management tone, guidance | Premium vendors or IR sites |
| **Twitter/X + Reddit** | Sentiment (noisy) | High false-positive risk for MF notes |
| **Sat imagery / card spend alts** | Thematic alt-data | Niche, paid |
| **LangChain document loaders + vector DB** | RAG over your own notes/PDFs | Great internal research layer |

### Roadmap (step by step)

| Step | Source | Status |
|------|--------|--------|
| **1** | **SEBI / BSE / company filings (PDF + RAG)** | **Done** |
| **2** | **AMFI / fund factsheets** | **Done** |
| **3** | **RBI / FRED macro** | **Done** |
| **4** | **Serper / DuckDuckGo search fallback** | **Done** |
| **5** | **Screener-style deep fundamentals** | **Done** |
| **6** | **Earnings transcripts** | **Done** |

### How to plug a new source into PruInsight

1. Add a `@tool` function in `pruinsight/tools/market_tools.py` or `filings_tools.py`.  
2. Register it (and bind it on the right agent).  
3. Document any API key in `.env` and this README.  
4. Keep agent prompts clear: when to call the tool and what not to invent.

---

## Prerequisites

- **Python 3.11+** recommended (for local non-Docker runs)  
- **Docker Desktop** (optional, for container deploy — see below)  
- API keys:
  - [Groq](https://console.groq.com/) — LLM (required)  
  - [Tavily](https://tavily.com/) — web / news / RBI search (required)  
  - [FRED](https://fred.stlouisfed.org/docs/api/api_key.html) — global macro series (optional)  
  - [LangSmith](https://smith.langchain.com) — LangGraph/LLM tracing (optional but recommended)

---

## Deploy with Docker (recommended for “it just runs”)

Full beginner walkthrough: **[DOCKER_LEARNING.md](./DOCKER_LEARNING.md)** (concepts + every command explained).

**Quick start** (Docker Desktop running, `.env` filled in project root):

```bash
# From project root
docker compose up --build
```

Open **http://localhost:8501**

```bash
docker compose down    # stop
```

| File | Role |
|------|------|
| `Dockerfile` | Image recipe (Python + deps + Streamlit) |
| `docker-compose.yml` | Ports + `.env` + one-command start |
| `.dockerignore` | Keeps secrets/junk out of the image |

Keys stay in `.env` (injected at **run** time). They are **not** copied into the image.

---

## Setup

### 1. Open the project folder

```bash
cd "path/to/pruinsight-agent"
```

### 2. Create and activate a virtual environment

**Always use this project’s `.venv`.** If you run system/`hermes` Python, you will see `ModuleNotFoundError: No module named 'langgraph'`.

| Shell | Activate |
|-------|----------|
| **PowerShell** | `python -m venv .venv` then `.\.venv\Scripts\Activate.ps1` |
| **Git Bash** | `python -m venv .venv` then `source .venv/Scripts/activate` |
| **cmd** | `python -m venv .venv` then `.venv\Scripts\activate.bat` |

Without activating, you can still call the venv Python directly:

```bash
# PowerShell / cmd
.\.venv\Scripts\python.exe main.py

# Git Bash
./.venv/Scripts/python.exe main.py
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

(or `.\.venv\Scripts\pip.exe install -r requirements.txt`)

### 4. Configure API keys

Create a `.env` file in the project root (same folder as `main.py`):

```env
GROQ_API_KEY=your_groq_key
TAVILY_API_KEY=your_tavily_key
# optional search fallback (Google SERP via serper.dev)
# SERPER_API_KEY=your_serper_key
# optional — better US rates / oil / VIX official series
# FRED_API_KEY=your_fred_key

# LangSmith tracing (https://smith.langchain.com) — auto-on when key is set
LANGSMITH_API_KEY=lsv2_your_key
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=pruinsight-agent

# Multi-model (optional) — different Groq models per agent role
# GROQ_MODEL_FAST=openai/gpt-oss-20b
# GROQ_MODEL_SMART=openai/gpt-oss-20b
# GROQ_MODEL_ANALYSIS=openai/gpt-oss-20b
```

### Multi-model optimization

Agents can use different Groq models via roles in `pruinsight/llm.py`:

| Role | Typical use | Env var |
|------|-------------|---------|
| `tool_loop` / `fast` | Researcher tool rounds | `GROQ_MODEL_FAST` |
| `analysis` | Filings, fundamentals, MF, macro, risk, transcripts | `GROQ_MODEL_ANALYSIS` |
| `synthesizer` / `smart` | Final IC note | `GROQ_MODEL_SMART` |
| `default` | Fallback | `GROQ_MODEL_DEFAULT` |

**Recipe for speed/cost:** smaller model for `FAST`, stronger model for `SMART`.  
List models: [console.groq.com/docs/models](https://console.groq.com/docs/models)

See **`.env.example`** for a full template.

**LangSmith traces (after any run):**  
[smith.langchain.com](https://smith.langchain.com) → project **pruinsight-agent**

**LangSmith Studio (visual graph IDE):**

```bash
pip install -U "langgraph-cli[inmem]"
pip install -e .
langgraph dev
# open Studio URL → select graph "pruinsight"
```

Full steps: **[LANGSMITH_STUDIO_SETUP.md](./LANGSMITH_STUDIO_SETUP.md)**  
Sample input: `studio_input.example.json`

Do **not** commit `.env` (it is listed in `.gitignore`).

---

## How to use the application

### Option A — Streamlit web UI (recommended)

1. From the project root, with the venv active (or using the venv Python path):

   ```bash
   # After activate:
   streamlit run streamlit_app.py

   # Or without activate:
   .\.venv\Scripts\python.exe -m streamlit run streamlit_app.py
   ```

2. Browser opens (usually `http://localhost:8501`).

3. **Sidebar** — system status, 8-agent pipeline, tools, desk presets  

4. **Main desk**
   - Navy masthead with live **Nifty / Sensex / India VIX / USD-INR** tape  
   - Research question + NSE symbols  
   - Toggles: **Charts & KPIs**, **Agent workpapers**  
   - Click **Run research pipeline** (or load a desk preset)

5. Watch the **live 8-agent stepper** (typically **1–3 minutes**).

6. **Results**
   - **Overview** — KPI cards (price, change, P/E, P/B, ROE, 52w range) + executive snapshot  
   - **Charts** — Altair price history and peer comparison  
   - **Research note** — masthead + section tabs (or full scroll)  
   - **Workpapers** — Ready/Thin status + each agent's brief  
   - **Export & sources** — Markdown, PDF, plain text, data-sources appendix

---

### Option B — Command-line interface (CLI)

```bash
# Default sample
python main.py

# Custom query
python main.py "Outlook on Reliance Industries for large-cap funds"

# Pass NSE symbols explicitly
python main.py "Compare private banks" -s HDFCBANK ICICIBANK KOTAKBANK

# Print each agent's intermediate brief + final report
python main.py "TCS vs Infosys" -s TCS INFY -v

# Also save PDF (includes Data sources appendix)
python main.py "HDFC Bank for MF desk" -s HDFCBANK --pdf hdfc_note.pdf
```

| Flag | Meaning |
|------|---------|
| `query` (positional) | Research question |
| `-s` / `--symbols` | One or more NSE tickers |
| `-v` / `--verbose` | Print market research, fundamentals, and risk before the final note |

---

## Tips for good results

- Prefer **clear company or sector** questions.  
- Pass **exact NSE symbols** (`HDFCBANK` not `HDFC`).  
- For peers, pass several symbols so `get_peer_snapshot` can compare.  
- Expect longer runs than a single-tool demo (multi-round tool calling).  
- Output is **balanced research framing**, not buy/sell ratings.

---

## Project layout

```
pruinsight-agent/
├── main.py                 # CLI entry
├── streamlit_app.py        # Streamlit research-desk UI
├── .streamlit/config.toml  # Navy/gold theme
├── requirements.txt
├── .env                    # API keys (local only — do not commit)
├── .gitignore
├── README.md
└── pruinsight/
    ├── state.py            # Shared LangGraph AgentState
    ├── llm.py              # Groq chat model helper
    ├── graph.py            # StateGraph wiring
    ├── runner.py           # Shared run_research() for CLI + UI
    ├── report_export.py    # Data sources appendix + Markdown/PDF export
    ├── viz_data.py         # KPI/chart data + report section parser
    ├── ui_theme.py         # Research-desk CSS + HTML fragments
    ├── tracing.py          # LangSmith enable + run tags/metadata
    ├── rag/
    │   └── store.py        # BM25 filings chunk store
    ├── tools/
    │   ├── market_tools.py # Quotes, news, indices, peers
    │   ├── filings_tools.py# Company filing search / PDF / RAG
    │   ├── search_providers.py  # Tavily → Serper → DuckDuckGo cascade
    │   ├── deep_fundamentals.py # Screener-style ratios / quarterly / peers
    │   ├── transcripts_tools.py # Earnings call transcript search + RAG
    │   ├── amfi_tools.py   # AMFI NAV + fund factsheet tools
    │   └── macro_tools.py  # RBI search + FRED/Yahoo macro
    └── agents/
        ├── tool_loop.py
        ├── researcher.py
        ├── filings.py
        ├── transcripts.py  # Earnings transcripts agent
        ├── fundamentals.py
        ├── mf_context.py
        ├── macro.py
        ├── risk.py
        └── synthesizer.py
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: No module named 'langgraph'` | Use project `.venv` (`.\.venv\Scripts\python.exe …`) |
| Streamlit / CLI says missing API key | Put keys in `.env`, restart app |
| Empty or thin stock data | Check NSE symbol; Yahoo may rate-limit or omit fields |
| Sparse analyst data on Indian names | Normal for Yahoo — treat Street view as optional |
| Search failures | Verify `TAVILY_API_KEY` / quota |
| LLM errors | Verify `GROQ_API_KEY` and model availability |

**Confirm which Python is running:**

```bash
python -c "import sys; print(sys.executable)"
# Should point at ...\pruinsight-agent\.venv\Scripts\python.exe
```

---

## Disclaimer

This project is for **learning multi-agent LangGraph patterns** and educational demos only.

- It does **not** constitute investment advice, a recommendation, or an offer to buy or sell securities.  
- Data may be delayed, incomplete, or incorrect.  
- Always do independent due diligence and consult licensed professionals.  
- Views generated by the agents are **not** official positions of ICICI Prudential Asset Management Company Limited.

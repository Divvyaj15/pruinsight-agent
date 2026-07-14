# PruInsight Agent

**PruInsight** is a multi-agent equity research demo built with **LangGraph**, **Groq**, **Tavily**, and **yfinance**.

It produces a structured mutual-fund-style research note for Indian (NSE) stocks — news context, fundamentals, risks, and a final synthesized report. Use it from the **command line** or a **Streamlit web UI**.

> **Educational / demo only.** Not investment advice and not an official ICICI Prudential AMC product.

---

## What it does

You give PruInsight a research question (and optionally NSE symbols). Four specialized agents run in sequence and hand work to each other:

```
Your query
    │
    ▼
┌────────────────────┐
│ 1. Market Researcher │  Web + news search, company headlines, index regime
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ 2. Filings Analyst   │  SEBI/BSE/NSE/IR PDFs → extract → BM25 RAG
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ 3. Fundamentals      │  Quote, financials, history, peers, Street targets
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ 4. MF Context (AMFI) │  Official NAVs + fund factsheet RAG
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ 5. Risk Assessor     │  Risks + optional vol / India VIX context
└─────────┬──────────┘
          ▼
┌────────────────────┐
│ 6. Report Synthesizer│  One IC-style note for an MF desk + disclaimer
└────────────────────┘
```

| Agent | What it contributes | Tools used |
|-------|---------------------|------------|
| **Market Researcher** | Headlines, catalysts, sector/macro story | `web_search`, `news_search`, `get_company_news`, `get_index_snapshot` |
| **Filings Analyst** | Primary-source excerpts from PDFs | `search_company_filings`, `ingest_filing_pdf`, `query_filings_rag` |
| **Fundamentals Analyst** | Metrics, statements, performance, peers | `get_stock_data`, `get_financials`, `get_price_history`, `get_analyst_view`, `get_peer_snapshot` |
| **MF Context** | AMFI schemes/NAVs + factsheet excerpts | `search_amfi_schemes`, `get_amfi_nav`, `search_related_equity_funds`, factsheet search/ingest/RAG |
| **Risk Assessor** | Risks, monitoring checklist | `get_price_history`, `get_index_snapshot` (+ prior agent text) |
| **Report Synthesizer** | Final PruInsight note | LLM only (merges everything) |

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
| 3 | RBI DBIE / FRED macro | Next |
| 4 | Serper or DuckDuckGo search fallback | Planned |
| 5 | Screener / CMIE-style deep fundamentals | Planned |
| 6 | Earnings transcripts | Planned |

### How to plug a new source into PruInsight

1. Add a `@tool` function in `pruinsight/tools/market_tools.py` or `filings_tools.py`.  
2. Register it (and bind it on the right agent).  
3. Document any API key in `.env` and this README.  
4. Keep agent prompts clear: when to call the tool and what not to invent.

---

## Prerequisites

- **Python 3.11+** recommended  
- API keys:
  - [Groq](https://console.groq.com/) — LLM  
  - [Tavily](https://tavily.com/) — web / news search  

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
```

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

3. **Sidebar**
   - Shows whether `GROQ_API_KEY` and `TAVILY_API_KEY` are loaded  
   - Explains the 4-agent pipeline  
   - Lists **research tools**  
   - **Examples** dropdown — pick a preset and click **Apply example**

4. **Main form**
   - **Research query** — free-text question  
   - **NSE symbols** — optional, comma-separated, **without** `.NS`  
   - **Show agent intermediates** — tabs for each agent’s draft  
   - Click **Generate research note**

5. Wait **~30–90 seconds** (more tools = more API calls).

6. **Results**
   - Intermediate tabs: Market Research, Fundamentals, Risk, Pipeline  
   - **Final PruInsight note** — full markdown report  
   - **Download note (.md)** or **Download note (.pdf)** — save the report locally  
   - **Data sources** section at the bottom of every note (Groq, Tavily, Yahoo Finance/yfinance, exchange/company PDFs + URLs ingested that run)

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
├── streamlit_app.py        # Streamlit web UI
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
    ├── rag/
    │   └── store.py        # BM25 filings chunk store
    ├── tools/
    │   ├── market_tools.py # Quotes, news, indices, peers
    │   ├── filings_tools.py# Company filing search / PDF / RAG
    │   └── amfi_tools.py   # AMFI NAV + fund factsheet tools
    └── agents/
        ├── tool_loop.py    # Shared multi-round tool calling
        ├── researcher.py
        ├── filings.py      # Primary-source filings agent
        ├── fundamentals.py
        ├── mf_context.py   # AMFI + factsheet MF desk agent
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

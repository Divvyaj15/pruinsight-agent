# LangSmith Studio setup (PruInsight)

There are **two related things** people call “LangSmith Studio”:

| Name | What it is | You need |
|------|------------|----------|
| **LangSmith (web traces)** | Dashboard for runs/traces after you run CLI/Streamlit | API key in `.env` only |
| **LangSmith Studio** (agent IDE) | Visual UI to **see the graph**, step through nodes, send test inputs | API key + `langgraph dev` + `langgraph.json` |

This guide covers **Studio** (the visual IDE) for **this repo**.  
Official docs: [LangSmith Studio](https://docs.langchain.com/oss/python/langgraph/studio)

---

## What Studio looks like when working

```
Your PC                         LangSmith cloud UI
────────                        ─────────────────
langgraph dev  ──local API──►   smith.langchain.com/studio
   │                            (graph diagram + chat/run panel)
   ▼
PruInsight graph (8 nodes)
```

- Local server default: `http://127.0.0.1:2024`  
- Studio UI:  
  `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`

---

## Prerequisites

1. **Python 3.11+** (this project uses 3.11)  
2. **LangSmith account** — [smith.langchain.com](https://smith.langchain.com)  
3. **LangSmith API key** — Settings → API Keys  
4. Project folder: `pruinsight-agent`  
5. `.env` with at least:

```env
GROQ_API_KEY=...
TAVILY_API_KEY=...

LANGSMITH_API_KEY=lsv2_...
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=pruinsight-agent
```

Files already added for Studio:

| File | Role |
|------|------|
| `langgraph.json` | Points Studio at our graph |
| `pyproject.toml` | Makes package installable for `langgraph dev` |
| `studio_input.example.json` | Sample state for a run |
| `pruinsight/graph.py:app` | Compiled LangGraph export |

---

## Step-by-step (Windows)

### 1. Go to the project

```powershell
cd "C:\Users\divvy\OneDrive\Desktop\Agentic AI Learning\pruinsight-agent"
```

### 2. Activate venv and install Studio CLI

```powershell
.\.venv\Scripts\Activate.ps1
pip install -U "langgraph-cli[inmem]"
pip install -e .
```

`pip install -e .` installs the local `pruinsight` package so Studio can import it.

### 3. Confirm `.env` has LangSmith key

```env
LANGSMITH_API_KEY=lsv2_your_key_here
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=pruinsight-agent
GROQ_API_KEY=...
TAVILY_API_KEY=...
```

### 4. Start the local Agent server

```powershell
langgraph dev
```

You should see something like:

- API on `http://127.0.0.1:2024`  
- Studio URL printed in the terminal  

**Safari tip:** Safari blocks some localhost Studio connections. Prefer **Chrome/Edge**, or:

```powershell
langgraph dev --tunnel
```

Then in Studio click **Connect to a local server** and paste the tunnel URL if needed.

### 5. Open Studio

Either:

- Click the Studio link from the terminal, or  
- Open:  
  [https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024](https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024)

Log in with the **same LangSmith account** as the API key.

### 6. Select the graph

In Studio, choose graph: **`pruinsight`**  
(defined in `langgraph.json` → `./pruinsight/graph.py:app`)

You should see the **8-node sequential graph**:

```text
researcher → filings → transcripts → fundamentals
  → mf_context → macro → risk → synthesizer
```

### 7. Run a test input

Use input shaped like `studio_input.example.json`:

```json
{
  "query": "Latest insights on HDFC Bank for mutual fund perspective",
  "symbols": ["HDFCBANK"],
  "market_research": "",
  "filings_context": "",
  "transcripts_context": "",
  "fundamentals": "",
  "mf_context": "",
  "macro_context": "",
  "risk_assessment": "",
  "final_report": "",
  "messages": []
}
```

**Important:** Pass **all** state keys (empty strings for intermediates).  
That matches `AgentState` used by the graph.

Click **Run** / submit.  
Watch nodes light up as each agent runs (this can take **1–3+ minutes** — many tools + LLMs).

### 8. Inspect results

In Studio / LangSmith:

- Graph path and node order  
- State after each node (`market_research`, `filings_context`, …, `final_report`)  
- LLM prompts & tool calls  
- Errors / latency  

Also under **Projects → pruinsight-agent** in the main LangSmith UI for full traces.

---

## Studio vs normal app

| | CLI / Streamlit | LangSmith Studio |
|--|-----------------|------------------|
| How to start | `python main.py` / `streamlit run` | `langgraph dev` |
| UI | Terminal / localhost:8501 | smith.langchain.com/studio |
| Graph view | No | Yes |
| Best for | Full product UX + charts | Debugging agents / structure |
| Tracing | Yes (if key set) | Yes + interactive graph |

You can use **both**: Studio for debugging the graph, Streamlit for the research desk UI.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `langgraph: command not found` | Activate venv; `pip install "langgraph-cli[inmem]"` |
| Graph not found | Check `langgraph.json` path `./pruinsight/graph.py:app` |
| Import errors | `pip install -e .` from project root |
| No API key / auth errors | Fix `LANGSMITH_API_KEY` in `.env` |
| Studio blank / can’t connect | Use Chrome/Edge; try `langgraph dev --tunnel` |
| Run fails missing state keys | Paste full `studio_input.example.json` |
| Run very slow | Normal for 8 agents + PDFs; start with one symbol |
| Want no cloud data | `LANGSMITH_TRACING=false` (Studio may still need account for UI) |

---

## Quick command card

```powershell
cd "C:\Users\divvy\OneDrive\Desktop\Agentic AI Learning\pruinsight-agent"
.\.venv\Scripts\Activate.ps1
pip install -U "langgraph-cli[inmem]"
pip install -e .

# Ensure .env has LANGSMITH_API_KEY + GROQ + TAVILY

langgraph dev
# → open Studio URL from terminal
# → select graph "pruinsight"
# → paste studio_input.example.json and Run
```

---

## Files reference

```text
langgraph.json              # Studio config
pyproject.toml              # package install for langgraph dev
studio_input.example.json   # sample AgentState input
pruinsight/graph.py         # app = compile()  ← Studio entry
pruinsight/tracing.py       # LangSmith env setup
.env                        # your keys (never commit)
```

Official: [docs.langchain.com — LangSmith Studio](https://docs.langchain.com/oss/python/langgraph/studio)

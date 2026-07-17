"""
PruInsight — multi-agent equity research (LangGraph + Groq).

Pipeline:
  Researcher → Filings → Transcripts → Fundamentals → MF → Macro → Risk → Synthesizer
"""

import argparse
import sys

# Windows consoles often default to cp1252; force UTF-8 for ₹ and em-dashes
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

load_dotenv()

from pruinsight.runner import run_research
from pruinsight.tracing import configure_tracing, tracing_status


def run(query: str, symbols: list[str] | None = None) -> str:
    """Invoke the multi-agent graph and return the final report."""
    result = run_research(query, symbols, source="cli")
    return result.get("final_report") or "(no report generated)"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PruInsight multi-agent research note generator"
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="Latest insights on HDFC Bank for mutual fund perspective in 2026",
        help="Research question / brief",
    )
    parser.add_argument(
        "--symbols",
        "-s",
        nargs="*",
        default=None,
        help="Optional NSE symbols (e.g. HDFCBANK RELIANCE)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print intermediate agent outputs",
    )
    parser.add_argument(
        "--pdf",
        metavar="PATH",
        default=None,
        help="Also save the final report as a PDF (e.g. report.pdf)",
    )
    args = parser.parse_args()

    print("=== PruInsight Multi-Agent ===")
    print(f"Query: {args.query}")
    if args.symbols:
        print(f"Symbols: {', '.join(args.symbols)}")
    print(
        "Running agents: researcher → filings → transcripts → fundamentals → mf → macro → risk → synthesizer ...\n"
    )

    ts = configure_tracing()
    if ts.get("enabled"):
        print(
            f"LangSmith tracing: ON  project={ts.get('project')}  "
            f"(https://smith.langchain.com)\n"
        )
    else:
        print(
            "LangSmith tracing: OFF  "
            "(add LANGSMITH_API_KEY to .env to enable)\n"
        )

    result = run_research(
        args.query,
        [s.upper() for s in (args.symbols or [])],
        source="cli",
    )

    if args.verbose:
        print("--- Market Research ---\n")
        print(result.get("market_research") or "N/A")
        print("\n--- Filings / Primary Sources ---\n")
        print(result.get("filings_context") or "N/A")
        print("\n--- Earnings Transcripts ---\n")
        print(result.get("transcripts_context") or "N/A")
        print("\n--- Fundamentals ---\n")
        print(result.get("fundamentals") or "N/A")
        print("\n--- MF / AMFI Context ---\n")
        print(result.get("mf_context") or "N/A")
        print("\n--- Macro / RBI / Global ---\n")
        print(result.get("macro_context") or "N/A")
        print("\n--- Risk Assessment ---\n")
        print(result.get("risk_assessment") or "N/A")
        print("\n--- Final Report ---\n")

    print(result.get("final_report") or "(no report generated)")

    if args.pdf:
        from pruinsight.report_export import save_report_pdf

        path = save_report_pdf(
            result.get("final_report") or "",
            args.pdf,
            title="PruInsight Research Note",
        )
        print(f"\nPDF saved to: {path}")


if __name__ == "__main__":
    main()

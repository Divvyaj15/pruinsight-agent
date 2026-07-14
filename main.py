"""
PruInsight — multi-agent equity research (LangGraph + Groq).

Pipeline:
  Researcher → Filings → Fundamentals → MF Context (AMFI) → Risk → Synthesizer
"""

import argparse
import sys

# Windows consoles often default to cp1252; force UTF-8 for ₹ and em-dashes
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv

load_dotenv()

from pruinsight.runner import run_research


def run(query: str, symbols: list[str] | None = None) -> str:
    """Invoke the multi-agent graph and return the final report."""
    result = run_research(query, symbols)
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
        "Running agents: researcher → filings → fundamentals → mf_context → risk → synthesizer ...\n"
    )

    result = run_research(
        args.query,
        [s.upper() for s in (args.symbols or [])],
    )

    if args.verbose:
        print("--- Market Research ---\n")
        print(result.get("market_research") or "N/A")
        print("\n--- Filings / Primary Sources ---\n")
        print(result.get("filings_context") or "N/A")
        print("\n--- Fundamentals ---\n")
        print(result.get("fundamentals") or "N/A")
        print("\n--- MF / AMFI Context ---\n")
        print(result.get("mf_context") or "N/A")
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

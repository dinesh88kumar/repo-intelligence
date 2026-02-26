"""
Repository Intelligence System — CLI Entry Point.

Usage:
    uv run python main.py                              # Analyse ./sample_applications/shop_app
    uv run python main.py /path/to/repo                # Analyse a specific repo
    uv run python main.py /path/to/repo --stream       # Stream progress updates
    uv run python main.py /path/to/repo --output report.md  # Save report to file
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Any, Dict

from langchain_ollama.llms import OllamaLLM

from config.settings import load_settings
from graph.workflow import build_graph

# ── Logging setup ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("repo-intelligence")


def _build_initial_state(repo_path: str) -> Dict[str, Any]:
    """Construct the initial pipeline state."""
    return {
        "repo_path": repo_path,
        "repo_tree": "",
        "key_files": "",
        "tech_stack": "",
        "business_summary": "",
        "evidence": [],
        "final_report": "",
        "entities": {},
        "workflows": {},
        "business_context": {},
        "architecture": {},
        "complexity_metrics": {},
        "dependencies": {},
        "gap_analysis": {},
        "errors": [],
    }


def run_sync(app: Any, repo_path: str) -> str:
    """Run the pipeline synchronously and return the final report."""
    initial_state = _build_initial_state(repo_path)

    logger.info("Starting analysis of: %s", repo_path)
    start = time.time()

    result = app.invoke(initial_state)

    elapsed = time.time() - start
    logger.info("Analysis completed in %.1f seconds", elapsed)

    return result.get("final_report", "No report generated.")


def run_streaming(app: Any, repo_path: str) -> str:
    """Run the pipeline with streaming progress updates."""
    initial_state = _build_initial_state(repo_path)

    logger.info("Starting streaming analysis of: %s", repo_path)
    start = time.time()

    final_report = ""
    for step_output in app.stream(initial_state):
        for node_name, node_state in step_output.items():
            elapsed = time.time() - start
            print(f"\n{'─' * 60}")
            print(f"✅ {node_name} completed ({elapsed:.1f}s)")

            # Show progress details
            if node_name == "scan_repo":
                evidence = node_state.get("evidence", [])
                print(f"   📁 Found {len(evidence)} key files")
            elif node_name == "extract_entities":
                entities = node_state.get("entities", {})
                print(f"   🏷️  {len(entities.get('domain_entities', []))} entities, "
                      f"{len(entities.get('api_endpoints', []))} endpoints")
            elif node_name == "analyse_workflows":
                wf = node_state.get("workflows", {})
                print(f"   🔀 {len(wf.get('primary_flows', []))} flows detected")
            elif node_name == "business_context":
                ctx = node_state.get("business_context", {})
                print(f"   💼 Domain: {ctx.get('domain', 'unknown')}")
            elif node_name == "analyse_architecture":
                arch = node_state.get("architecture", {})
                print(f"   🏗️  Pattern: {arch.get('pattern', 'unknown')}")
            elif node_name == "gap_analysis":
                gap = node_state.get("gap_analysis", {})
                print(f"   📊 Maturity: {gap.get('maturity_score', 0)}/100")
            elif node_name == "generate_report":
                final_report = node_state.get("final_report", "")
                print(f"   📝 Report: {len(final_report)} characters")

    total = time.time() - start
    print(f"\n{'═' * 60}")
    print(f"🏁 Analysis completed in {total:.1f}s")

    return final_report


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AI Repository Intelligence System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "repo_path",
        nargs="?",
        default="./sample_applications/shop_app",
        help="Path to the repository to analyse (default: ./sample_applications/shop_app)",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Enable streaming progress updates",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Save report to a file instead of stdout",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override the LLM model name (default from config)",
    )

    args = parser.parse_args()

    # Load config
    settings = load_settings()
    model_name = args.model or settings.llm.model_name

    # Build pipeline
    llm = OllamaLLM(model=model_name)
    app = build_graph(llm)

    # Execute
    if args.stream:
        report = run_streaming(app, args.repo_path)
    else:
        report = run_sync(app, args.repo_path)

    # Output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        logger.info("Report saved to %s", args.output)
    else:
        print("\n" + report)


if __name__ == "__main__":
    main()

"""
LangGraph workflow orchestration — full pipeline from Phase 1 through Phase 5.

Pipeline stages:
1. scan_repo → repo scan + tech stack + dependencies
2. extract_entities → domain entity extraction
3. analyse_workflows → workflow inference
4. business_context → structured business analysis
5. analyse_architecture → architecture pattern detection
6. gap_analysis → best practices comparison
7. generate_report → executive Markdown report

Supports both sync (.invoke) and streaming (.stream) execution.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, StateGraph

from agents.architecture_analyzer import architecture_analyzer_agent
from agents.business_context import business_context_agent
from agents.entity_extractor import entity_extractor_agent
from agents.gap_analyzer import gap_analyzer_agent
from agents.repo_scanner import repo_scanner_agent
from agents.report_generator import report_generator_agent
from agents.workflow_analyzer import workflow_analyzer_agent
from state import AgentState

logger = logging.getLogger(__name__)


def build_graph(llm: Any) -> Any:
    """
    Construct and compile the full analysis pipeline.

    Args:
        llm: A LangChain-compatible LLM (e.g. OllamaLLM).

    Returns:
        Compiled LangGraph StateGraph ready for .invoke() or .stream().
    """
    graph = StateGraph(AgentState)

    # ── Register nodes ────────────────────────────────────
    graph.add_node("scan_repo", lambda s: repo_scanner_agent(llm, s))
    graph.add_node("extract_entities", lambda s: entity_extractor_agent(llm, s))
    graph.add_node("analyse_workflows", lambda s: workflow_analyzer_agent(llm, s))
    graph.add_node("business_context", lambda s: business_context_agent(llm, s))
    graph.add_node("analyse_architecture", lambda s: architecture_analyzer_agent(llm, s))
    graph.add_node("gap_analysis", lambda s: gap_analyzer_agent(llm, s))
    graph.add_node("generate_report", report_generator_agent)

    # ── Define edges (linear pipeline) ────────────────────
    graph.set_entry_point("scan_repo")

    graph.add_edge("scan_repo", "extract_entities")
    graph.add_edge("extract_entities", "analyse_workflows")
    graph.add_edge("analyse_workflows", "business_context")
    graph.add_edge("business_context", "analyse_architecture")
    graph.add_edge("analyse_architecture", "gap_analysis")
    graph.add_edge("gap_analysis", "generate_report")
    graph.add_edge("generate_report", END)

    compiled = graph.compile()
    logger.info("Analysis pipeline compiled with 7 nodes")
    return compiled

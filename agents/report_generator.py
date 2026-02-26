"""
Executive Report Generator — produces a comprehensive Markdown report.

Includes: business summary, architecture overview, maturity score,
risk heatmap, prioritised recommendations, and evidence citations.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _format_list(items: List[str], bullet: str = "•") -> str:
    """Format a list of strings as bullet points."""
    if not items:
        return "_None detected._"
    return "\n".join(f"  {bullet} {item}" for item in items)


def _severity_emoji(score: int) -> str:
    """Return an emoji indicator based on maturity score."""
    if score >= 80:
        return "🟢"
    if score >= 60:
        return "🟡"
    if score >= 40:
        return "🟠"
    return "🔴"


def _risk_heatmap(gap_analysis: Dict[str, Any]) -> str:
    """Generate a textual risk heatmap."""
    risks = gap_analysis.get("risks", [])
    security = gap_analysis.get("security_issues", [])
    gaps = gap_analysis.get("gaps", [])

    lines: List[str] = []

    if security:
        lines.append("### 🔴 Critical — Security")
        for issue in security:
            lines.append(f"  ⚠️  {issue}")

    if risks:
        lines.append("\n### 🟠 High — Technical Risks")
        for risk in risks:
            lines.append(f"  ⚠️  {risk}")

    if gaps:
        lines.append("\n### 🟡 Medium — Practice Gaps")
        for gap in gaps:
            lines.append(f"  📋 {gap}")

    if not lines:
        lines.append("  ✅ No significant risks detected.")

    return "\n".join(lines)


def report_generator_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate the full executive report from pipeline state.

    This is a pure formatting function with no LLM calls — it assembles
    all prior analysis results into a clean Markdown document.

    Args:
        state: Final pipeline state with all analysis results.

    Returns:
        Dict with 'final_report' key containing Markdown string.
    """
    # ── Extract data from state ───────────────────────────
    business_ctx = state.get("business_context", {})
    architecture = state.get("architecture", {})
    metrics = state.get("complexity_metrics", {})
    entities = state.get("entities", {})
    workflows = state.get("workflows", {})
    gap_analysis = state.get("gap_analysis", {})
    evidence = state.get("evidence", [])
    dependencies = state.get("dependencies", {})

    maturity = gap_analysis.get("maturity_score", 0)
    emoji = _severity_emoji(maturity)

    # ── Build report sections ─────────────────────────────
    sections: List[str] = []

    # Header
    sections.append("# 🧠 Repository Intelligence Report\n")
    sections.append(f"**Maturity Score: {emoji} {maturity}/100**\n")

    # Business summary
    sections.append("---\n## 💼 Business Context\n")
    domain = business_ctx.get("domain", state.get("business_summary", "Not analysed."))
    sections.append(f"**Domain:** {domain}\n")

    users = business_ctx.get("primary_users", [])
    if users:
        sections.append(f"**Target Users:** {', '.join(users)}\n")

    features = business_ctx.get("core_features", [])
    if features:
        sections.append("**Core Features:**")
        sections.append(_format_list(features))

    biz_workflows = business_ctx.get("business_workflows", [])
    if biz_workflows:
        sections.append("\n**Business Workflows:**")
        sections.append(_format_list(biz_workflows))

    confidence = business_ctx.get("confidence_score", 0)
    if confidence:
        sections.append(f"\n_Analysis confidence: {confidence:.0%}_")

    # Tech stack
    sections.append("\n---\n## 🔧 Tech Stack\n")
    sections.append(state.get("tech_stack", "Not detected."))

    # Languages breakdown
    languages = metrics.get("languages", {})
    if languages:
        sections.append("\n**Language Distribution (LOC):**")
        for lang, loc in sorted(languages.items(), key=lambda x: -x[1]):
            sections.append(f"  • {lang}: {loc:,} lines")

    # Architecture
    sections.append("\n---\n## 🏗️ Architecture Overview\n")
    arch_pattern = architecture.get("pattern", "unknown")
    sections.append(f"**Pattern:** {arch_pattern}")
    sections.append(f"**API Style:** {architecture.get('api_style', 'unknown')}")
    sections.append(f"**Auth:** {architecture.get('auth_mechanism', 'unknown')}")
    sections.append(f"**Database:** {architecture.get('database_type', 'unknown')}")

    layers = architecture.get("layers", [])
    if layers:
        sections.append(f"\n**Layers:** {' → '.join(layers)}")

    # Complexity metrics
    sections.append("\n---\n## 📊 Complexity Metrics\n")
    sections.append(f"| Metric | Value |")
    sections.append(f"|--------|-------|")
    sections.append(f"| Total Files | {metrics.get('total_files', 'N/A')} |")
    sections.append(f"| Lines of Code | {metrics.get('total_loc', 'N/A'):,} |")
    sections.append(f"| Service Count | {metrics.get('service_count', 'N/A')} |")
    sections.append(f"| Test Coverage | {metrics.get('test_coverage_heuristic', 'N/A')} |")

    # Domain entities
    sections.append("\n---\n## 🏷️ Domain Entities\n")
    domain_entities = entities.get("domain_entities", [])
    api_endpoints = entities.get("api_endpoints", [])
    db_models = entities.get("database_models", [])
    integrations = entities.get("external_integrations", [])

    if domain_entities:
        sections.append("**Models:** " + ", ".join(domain_entities))
    if api_endpoints:
        sections.append("\n**API Endpoints:**")
        sections.append(_format_list(api_endpoints))
    if db_models:
        sections.append("\n**Database Models:** " + ", ".join(db_models))
    if integrations:
        sections.append("\n**External Integrations:** " + ", ".join(integrations))

    # Workflows
    sections.append("\n---\n## 🔀 Application Workflows\n")
    flows = workflows.get("primary_flows", [])
    req_paths = workflows.get("request_paths", [])
    bg_jobs = workflows.get("background_jobs", [])

    if flows:
        sections.append("**User Flows:**")
        sections.append(_format_list(flows))
    if req_paths:
        sections.append("\n**Request Paths:**")
        sections.append(_format_list(req_paths))
    if bg_jobs:
        sections.append("\n**Background Jobs:**")
        sections.append(_format_list(bg_jobs))

    # Dependencies
    circular = dependencies.get("circular_dependencies", [])
    coupling = dependencies.get("high_coupling_modules", [])
    if circular or coupling:
        sections.append("\n---\n## 🔗 Dependency Analysis\n")
        if circular:
            sections.append("**⚠️ Circular Dependencies:**")
            for cycle in circular[:5]:
                sections.append(f"  🔄 {' → '.join(cycle)}")
        if coupling:
            sections.append("\n**High-Coupling Modules:**")
            sections.append(_format_list(coupling))

    # Risk heatmap
    sections.append("\n---\n## 🔥 Risk Heatmap\n")
    sections.append(_risk_heatmap(gap_analysis))

    # Strengths
    strengths = gap_analysis.get("strengths", [])
    if strengths:
        sections.append("\n---\n## ✅ Strengths\n")
        sections.append(_format_list(strengths, "✓"))

    # Recommendations
    recommendations = gap_analysis.get("recommendations", [])
    if recommendations:
        sections.append("\n---\n## 📌 Prioritised Recommendations\n")
        for i, rec in enumerate(recommendations, 1):
            sections.append(f"  **{i}.** {rec}")

    # Evidence
    if evidence:
        sections.append("\n---\n## 📂 Evidence Files\n")
        for path in evidence[:20]:
            sections.append(f"  📄 `{path}`")

    # Footer
    sections.append("\n---\n_Generated by Repository Intelligence System v2.0_")

    report = "\n".join(sections)

    logger.info("Executive report generated: %d characters", len(report))
    return {"final_report": report}

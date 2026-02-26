"""
Gap Analyser Agent — compares the repository against best practices
and produces a structured gap analysis with maturity scoring.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate

from analysis.best_practices import Finding, Severity, evaluate_rules

logger = logging.getLogger(__name__)

_PROMPT = ChatPromptTemplate.from_template("""\
You are a senior engineering consultant reviewing a codebase.

Below are automated best-practice findings for this repository:

{findings_text}

Tech Stack: {tech_stack}
Architecture: {architecture}

Based on these findings, generate a concise executive-level gap analysis.

Return ONLY a JSON object (no markdown, no explanation):
- "strengths": list of 3-5 things the repo does well
- "gaps": list of 3-5 important gaps or missing practices
- "risks": list of 2-3 technical or business risks
- "recommendations": list of 3-5 prioritised action items (most important first)

Be specific and actionable. Reference concrete findings.
JSON:""")


def _findings_to_text(findings: List[Finding]) -> str:
    """Format findings for LLM consumption."""
    lines: List[str] = []
    for f in findings:
        status = "✅ PASS" if f.passed else "❌ FAIL"
        lines.append(
            f"- [{f.severity.value.upper()}] {status} {f.rule_name}: {f.description}"
        )
        if f.recommendation:
            lines.append(f"  → Recommendation: {f.recommendation}")
        if f.evidence:
            lines.append(f"  → Evidence: {f.evidence}")
    return "\n".join(lines)


def _compute_maturity_score(findings: List[Finding]) -> int:
    """
    Compute a 0–100 maturity score from findings.

    Weights: CRITICAL rules count more than INFO rules.
    """
    if not findings:
        return 0

    severity_weights = {
        Severity.CRITICAL: 20,
        Severity.HIGH: 15,
        Severity.MEDIUM: 10,
        Severity.LOW: 5,
        Severity.INFO: 2,
    }

    total_weight = 0
    earned_weight = 0

    for f in findings:
        w = severity_weights.get(f.severity, 5)
        total_weight += w
        if f.passed:
            earned_weight += w

    if total_weight == 0:
        return 0

    return min(100, round((earned_weight / total_weight) * 100))


def _extract_security_issues(findings: List[Finding]) -> List[str]:
    """Pull security-specific failed findings."""
    security_rules = {
        "hardcoded-secrets", "open-cors", "input-validation",
        "authentication", "env-files",
    }
    issues: List[str] = []
    for f in findings:
        if f.rule_name in security_rules and not f.passed:
            msg = f"{f.description}"
            if f.recommendation:
                msg += f" — {f.recommendation}"
            issues.append(msg)
    return issues


def _parse_json_safely(text: str) -> Dict[str, Any]:
    """Parse JSON from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse gap analysis JSON")
        return {
            "strengths": [],
            "gaps": [],
            "risks": [],
            "recommendations": [text[:300]],
        }


def gap_analyzer_agent(llm: Any, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run best-practice rules and LLM-based gap analysis.

    Args:
        llm: LangChain-compatible LLM.
        state: Current pipeline state.

    Returns:
        Dict with 'gap_analysis' key matching GapAnalysis schema.
    """
    repo_path = state.get("repo_path", ".")
    tech_stack = state.get("tech_stack", "")
    key_files = state.get("key_files", "")

    # Run rule engine
    findings = evaluate_rules(repo_path, key_files, tech_stack)
    findings_text = _findings_to_text(findings)

    # Compute maturity score deterministically
    maturity_score = _compute_maturity_score(findings)
    security_issues = _extract_security_issues(findings)

    # LLM-based synthesis
    architecture = state.get("architecture", {})
    chain = _PROMPT | llm
    raw = chain.invoke({
        "findings_text": findings_text,
        "tech_stack": tech_stack,
        "architecture": json.dumps(architecture, indent=2) if architecture else "Not analysed.",
    })

    analysis = _parse_json_safely(raw)
    analysis["maturity_score"] = maturity_score
    analysis["security_issues"] = security_issues

    logger.info(
        "Gap analysis complete: maturity=%d/100, %d gaps, %d risks",
        maturity_score,
        len(analysis.get("gaps", [])),
        len(analysis.get("risks", [])),
    )

    return {"gap_analysis": analysis}

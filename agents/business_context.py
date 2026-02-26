"""
Business Context Agent — upgraded from Phase 1.

Now outputs structured JSON matching the BusinessContext schema
instead of a free-text summary. The free-text summary is still
preserved in state['business_summary'] for backward compatibility.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

_PROMPT = ChatPromptTemplate.from_template("""\
You are an expert product analyst and business strategist.

Based on the repository information below, provide a deep business analysis.

Tech Stack:
{tech_stack}

Key Files:
{key_files}

Extracted Entities:
{entities}

Inferred Workflows:
{workflows}

Return ONLY a JSON object (no markdown, no explanation) with these keys:
- "domain": the business domain (e.g. "e-commerce", "fintech", "healthcare")
- "primary_users": list of target user types
- "core_features": list of main features/capabilities
- "business_workflows": list of key business process descriptions
- "confidence_score": float from 0.0 to 1.0 indicating your confidence

Also provide a concise 2-3 sentence human-readable summary in a key called "summary".
JSON:""")


def _parse_json_safely(text: str) -> Dict[str, Any]:
    """Parse JSON from LLM output, handling common formatting issues."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse business context JSON, returning defaults")
        return {
            "domain": "unknown",
            "primary_users": [],
            "core_features": [],
            "business_workflows": [],
            "confidence_score": 0.0,
            "summary": text[:500],
        }


def business_context_agent(llm: Any, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate structured business context from code analysis.

    Args:
        llm: LangChain-compatible LLM.
        state: Current pipeline state.

    Returns:
        Dict updating both 'business_summary' (str) and 'business_context' (structured).
    """
    entities = state.get("entities", {})
    workflows = state.get("workflows", {})

    chain = _PROMPT | llm
    raw = chain.invoke({
        "tech_stack": state.get("tech_stack", "unknown"),
        "key_files": state.get("key_files", "")[:6000],
        "entities": json.dumps(entities, indent=2) if entities else "Not extracted yet.",
        "workflows": json.dumps(workflows, indent=2) if workflows else "Not inferred yet.",
    })

    parsed = _parse_json_safely(raw)

    # Extract summary for backward compatibility
    summary = parsed.pop("summary", "")
    if not summary:
        summary = f"Domain: {parsed.get('domain', 'unknown')}. Features: {', '.join(parsed.get('core_features', [])[:3])}."

    logger.info(
        "Business context: domain=%s, confidence=%.2f",
        parsed.get("domain", "unknown"),
        parsed.get("confidence_score", 0.0),
    )

    return {
        "business_summary": summary,
        "business_context": parsed,
    }

"""
Workflow Analyser Agent — infers primary user flows, request→response paths,
and background jobs from the codebase.

Returns structured data matching the WorkflowInfo schema.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

_PROMPT = ChatPromptTemplate.from_template("""\
You are a senior backend engineer analysing application workflows.

Based on the code evidence below, infer the runtime behaviour of this application.

Tech Stack: {tech_stack}

Code Evidence:
{code_evidence}

Return ONLY a JSON object (no markdown, no explanation) with these keys:
- "primary_flows": list of primary user flow descriptions (e.g. "User registers → email verification → login")
- "request_paths": list of request→processing→response paths (e.g. "POST /orders → validate items → create order → return 201")
- "background_jobs": list of background tasks/jobs if any (e.g. "Email queue processor", "Nightly data sync")
- "evidence_files": list of file paths that provided evidence for the above

If a category has no entries, return an empty list.
JSON:""")


def _parse_json_safely(text: str) -> Dict[str, Any]:
    """Extract and parse JSON from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse workflow JSON, returning defaults")
        return {
            "primary_flows": [],
            "request_paths": [],
            "background_jobs": [],
            "evidence_files": [],
        }


def workflow_analyzer_agent(llm: Any, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Infer application workflows from code evidence.

    Args:
        llm: LangChain-compatible LLM.
        state: Current pipeline state.

    Returns:
        Dict with 'workflows' key matching WorkflowInfo schema.
    """
    code_evidence = state.get("key_files", "")
    if not code_evidence.strip():
        code_evidence = "No code evidence available."

    chain = _PROMPT | llm
    raw = chain.invoke({
        "tech_stack": state.get("tech_stack", "unknown"),
        "code_evidence": code_evidence[:8000],
    })

    workflows = _parse_json_safely(raw)

    logger.info(
        "Inferred workflows: %d flows, %d request paths, %d background jobs",
        len(workflows.get("primary_flows", [])),
        len(workflows.get("request_paths", [])),
        len(workflows.get("background_jobs", [])),
    )

    return {"workflows": workflows}

"""
Entity Extractor Agent — extracts domain entities, APIs, DB models,
and external integrations from the codebase.

Returns structured JSON matching the EntityInfo schema.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

_PROMPT = ChatPromptTemplate.from_template("""\
You are a senior software architect performing domain analysis.

Analyse the following code evidence and extract structured information.

Tech Stack: {tech_stack}

Relevant Code:
{code_evidence}

Return ONLY a JSON object (no markdown, no explanation) with these keys:
- "domain_entities": list of domain model names (e.g. User, Order, Product)
- "api_endpoints": list of detected API routes (e.g. "GET /users", "POST /orders")
- "database_models": list of database table/model names
- "external_integrations": list of third-party services or APIs used

If a category has no entries, return an empty list.
JSON:""")


def _parse_json_safely(text: str) -> Dict[str, Any]:
    """Extract and parse JSON from LLM output, handling markdown fences."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse entity extraction JSON, returning defaults")
        return {
            "domain_entities": [],
            "api_endpoints": [],
            "database_models": [],
            "external_integrations": [],
        }


def entity_extractor_agent(llm: Any, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract domain entities from the codebase using semantic search results.

    Args:
        llm: LangChain-compatible LLM instance.
        state: Current pipeline state (must have tech_stack and key_files).

    Returns:
        Dict with 'entities' key matching EntityInfo schema.
    """
    code_evidence = state.get("key_files", "")

    # If semantic search results are available, prefer them
    if not code_evidence.strip():
        code_evidence = "No code evidence available."

    chain = _PROMPT | llm
    raw = chain.invoke({
        "tech_stack": state.get("tech_stack", "unknown"),
        "code_evidence": code_evidence[:8000],  # Limit context size
    })

    entities = _parse_json_safely(raw)

    logger.info(
        "Extracted entities: %d domain, %d APIs, %d models, %d integrations",
        len(entities.get("domain_entities", [])),
        len(entities.get("api_endpoints", [])),
        len(entities.get("database_models", [])),
        len(entities.get("external_integrations", [])),
    )

    return {"entities": entities}

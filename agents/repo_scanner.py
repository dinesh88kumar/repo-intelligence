"""
Repository Scanner Agent — scans the repo, detects tech stack,
and runs dependency analysis.

Enhanced from Phase 1 with dependency mapping and complexity awareness.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from langchain_core.prompts import ChatPromptTemplate

from tools.dependency_mapper import analyse_dependencies
from tools.repo_reader import scan_repository

logger = logging.getLogger(__name__)

_PROMPT = ChatPromptTemplate.from_template("""\
You are a senior software architect.

Based on the repository structure and key files,
identify the tech stack and frameworks used.

Repo Tree:
{tree}

Key Files:
{key_files}

Return a concise tech stack summary listing:
- Programming languages
- Frameworks (e.g. FastAPI, Express, Spring Boot)
- Databases (if detectable)
- Key libraries
- Build tools

Be factual — only list what you can see evidence for.\
""")


def repo_scanner_agent(llm: Any, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scan the repository, detect tech stack, and analyse dependencies.

    Args:
        llm: LangChain-compatible LLM.
        state: Current pipeline state (needs 'repo_path').

    Returns:
        Dict updating repo_tree, key_files, tech_stack, evidence, dependencies.
    """
    repo_path = state.get("repo_path", ".")

    # Scan filesystem
    tree, key_files, evidence = scan_repository(repo_path)
    logger.info("Repo scanned: %d evidence files found", len(evidence))

    # Detect tech stack via LLM
    chain = _PROMPT | llm
    tech_stack = chain.invoke({
        "tree": tree[:5000],
        "key_files": key_files[:6000],
    })

    # Run dependency analysis (deterministic, no LLM)
    dependencies = analyse_dependencies(repo_path)
    logger.info(
        "Dependencies: %d modules, %d circular chains",
        len(dependencies.get("module_graph", {})),
        len(dependencies.get("circular_dependencies", [])),
    )

    return {
        "repo_tree": tree,
        "key_files": key_files,
        "tech_stack": tech_stack,
        "evidence": evidence,
        "dependencies": dependencies,
    }

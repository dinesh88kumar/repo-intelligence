"""
Architecture Analyser Agent — detects architecture patterns in the codebase.

Detects: monolith vs microservices, layered architecture, MVC, REST vs GraphQL,
auth mechanism, database type. Always provides evidence.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from langchain_core.prompts import ChatPromptTemplate

from config.settings import ScanSettings, load_settings

logger = logging.getLogger(__name__)

_PROMPT = ChatPromptTemplate.from_template("""\
You are a senior software architect analysing a codebase.

Repo structure:
{repo_tree}

Tech stack: {tech_stack}

Key file contents:
{key_files}

Complexity metrics:
{metrics}

Dependency analysis:
{dependencies}

Analyse the architecture and return ONLY a JSON object (no markdown, no explanation):
- "pattern": one of "monolith", "microservices", "modular-monolith", "serverless", "unknown"
- "layers": list of architectural layers found (e.g. "controller", "service", "repository", "model")
- "api_style": one of "REST", "GraphQL", "gRPC", "WebSocket", "mixed", "none"
- "auth_mechanism": detected auth approach or "none"
- "database_type": detected database type or "none"
- "evidence": list of file paths or patterns that support your analysis

Be precise. Base your analysis on concrete evidence, not assumptions.
JSON:""")


def _compute_complexity_metrics(
    repo_path: str,
    settings: ScanSettings | None = None,
) -> Dict[str, Any]:
    """
    Compute basic complexity metrics for the repository.

    Returns a dict matching the ComplexityMetrics schema.
    """
    if settings is None:
        settings = load_settings().scan

    repo_path = os.path.abspath(repo_path)
    total_files = 0
    total_loc = 0
    languages: Dict[str, int] = {}
    test_files = 0

    ext_to_lang = {
        ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
        ".java": "Java", ".go": "Go", ".rs": "Rust", ".rb": "Ruby",
        ".php": "PHP", ".cs": "C#", ".kt": "Kotlin", ".scala": "Scala",
        ".swift": "Swift", ".c": "C", ".cpp": "C++",
    }

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in settings.skip_dirs]

        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in ext_to_lang:
                continue

            total_files += 1
            if total_files > settings.max_files:
                break

            lang = ext_to_lang[ext]
            full_path = os.path.join(root, fname)

            # Count LOC
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
                    line_count = sum(1 for line in fh if line.strip())
                total_loc += line_count
                languages[lang] = languages.get(lang, 0) + line_count
            except OSError:
                pass

            # Heuristic: test file detection
            name_lower = fname.lower()
            if "test" in name_lower or "spec" in name_lower:
                test_files += 1

    # Service count heuristic
    service_indicators = {"main.py", "app.py", "server.py", "index.js", "index.ts", "Application.java"}
    service_count = 0
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in settings.skip_dirs]
        for fname in files:
            if fname in service_indicators:
                service_count += 1

    test_ratio = test_files / max(total_files, 1)
    if test_ratio > 0.3:
        coverage_heuristic = "good (>30% test files)"
    elif test_ratio > 0.1:
        coverage_heuristic = "moderate (10-30% test files)"
    elif test_files > 0:
        coverage_heuristic = "low (<10% test files)"
    else:
        coverage_heuristic = "none detected"

    return {
        "total_files": total_files,
        "total_loc": total_loc,
        "service_count": service_count,
        "test_coverage_heuristic": coverage_heuristic,
        "languages": languages,
    }


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
        logger.warning("Failed to parse architecture JSON, returning defaults")
        return {
            "pattern": "unknown",
            "layers": [],
            "api_style": "unknown",
            "auth_mechanism": "unknown",
            "database_type": "unknown",
            "evidence": [],
        }


def architecture_analyzer_agent(llm: Any, state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyse the repository architecture using code structure and LLM.

    Args:
        llm: LangChain-compatible LLM.
        state: Current pipeline state.

    Returns:
        Dict with 'architecture', 'complexity_metrics' keys.
    """
    repo_path = state.get("repo_path", ".")
    metrics = _compute_complexity_metrics(repo_path)
    dependencies = state.get("dependencies", {})

    chain = _PROMPT | llm
    raw = chain.invoke({
        "repo_tree": state.get("repo_tree", "")[:4000],
        "tech_stack": state.get("tech_stack", "unknown"),
        "key_files": state.get("key_files", "")[:6000],
        "metrics": json.dumps(metrics, indent=2),
        "dependencies": json.dumps(dependencies, indent=2)[:3000] if dependencies else "Not analysed yet.",
    })

    architecture = _parse_json_safely(raw)

    logger.info(
        "Architecture: pattern=%s, api_style=%s, db=%s",
        architecture.get("pattern"),
        architecture.get("api_style"),
        architecture.get("database_type"),
    )

    return {
        "architecture": architecture,
        "complexity_metrics": metrics,
    }

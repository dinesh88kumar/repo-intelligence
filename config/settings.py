"""
Centralized configuration for the Repository Intelligence System.

All tunable parameters live here so nothing is hardcoded across the codebase.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class ScanSettings:
    """Controls repository scanning behaviour."""

    max_files: int = 2000
    max_file_size_bytes: int = 500_000  # 500 KB
    max_tree_depth: int = 12
    important_files: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "requirements.txt",
                "pyproject.toml",
                "setup.py",
                "setup.cfg",
                "package.json",
                "pom.xml",
                "build.gradle",
                "Dockerfile",
                "docker-compose.yml",
                "docker-compose.yaml",
                "README.md",
                "main.py",
                "app.py",
                "manage.py",
                "Makefile",
                ".env.example",
                "tsconfig.json",
                "go.mod",
                "Cargo.toml",
            }
        )
    )
    skip_dirs: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                ".git",
                ".svn",
                "__pycache__",
                "node_modules",
                ".venv",
                "venv",
                "env",
                ".tox",
                ".mypy_cache",
                ".pytest_cache",
                "dist",
                "build",
                ".eggs",
                ".idea",
                ".vscode",
                ".zencoder",
                ".zenflow",
            }
        )
    )


@dataclass(frozen=True)
class SemanticSearchSettings:
    """Controls the embeddings-based search pipeline."""

    chunk_size: int = 1500
    chunk_overlap: int = 200
    top_k: int = 10
    code_extensions: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                ".py",
                ".js",
                ".ts",
                ".jsx",
                ".tsx",
                ".java",
                ".go",
                ".rs",
                ".rb",
                ".php",
                ".cs",
                ".kt",
                ".scala",
                ".swift",
                ".c",
                ".cpp",
                ".h",
                ".hpp",
                ".yaml",
                ".yml",
                ".json",
                ".toml",
                ".xml",
                ".sql",
                ".graphql",
                ".proto",
                ".md",
            }
        )
    )


@dataclass(frozen=True)
class LLMSettings:
    """Controls LLM behaviour."""

    model_name: str = "qwen3:4b"
    temperature: float = 0.1
    max_retries: int = 2
    request_timeout: int = 120


@dataclass(frozen=True)
class ReportSettings:
    """Controls report generation."""

    include_evidence: bool = True
    max_evidence_lines: int = 30
    maturity_score_weights: dict[str, float] = field(
        default_factory=lambda: {
            "architecture": 0.25,
            "best_practices": 0.30,
            "security": 0.20,
            "documentation": 0.15,
            "testing": 0.10,
        }
    )


@dataclass(frozen=True)
class Settings:
    """Root configuration container."""

    scan: ScanSettings = field(default_factory=ScanSettings)
    search: SemanticSearchSettings = field(default_factory=SemanticSearchSettings)
    llm: LLMSettings = field(default_factory=LLMSettings)
    report: ReportSettings = field(default_factory=ReportSettings)


def load_settings() -> Settings:
    """Load settings, optionally overriding from environment variables."""

    llm_model = os.getenv("RI_LLM_MODEL", "qwen3:4b")
    max_files = int(os.getenv("RI_MAX_FILES", "2000"))
    chunk_size = int(os.getenv("RI_CHUNK_SIZE", "1500"))
    top_k = int(os.getenv("RI_TOP_K", "10"))

    return Settings(
        scan=ScanSettings(max_files=max_files),
        search=SemanticSearchSettings(chunk_size=chunk_size, top_k=top_k),
        llm=LLMSettings(model_name=llm_model),
    )

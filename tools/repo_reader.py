"""
Repository scanner tool — reads repo tree and key files.

Enhanced from Phase 1 with:
- configurable limits (max files, depth, file size)
- skip directories (.git, node_modules, etc.)
- logging
- safe encoding handling
"""

from __future__ import annotations

import logging
import os
from typing import List, Tuple

from config.settings import ScanSettings, load_settings

logger = logging.getLogger(__name__)


def scan_repository(
    repo_path: str,
    settings: ScanSettings | None = None,
) -> Tuple[str, str, List[str]]:
    """
    Walk the repository and return (tree, key_file_contents, evidence_paths).

    Args:
        repo_path: Absolute or relative path to the repository root.
        settings: Optional scan settings; defaults are loaded from config.

    Returns:
        tree: Indented string representation of the directory tree.
        key_contents: Concatenated important file contents (truncated).
        evidence: List of absolute paths of important files found.
    """
    if settings is None:
        settings = load_settings().scan

    repo_path = os.path.abspath(repo_path)
    if not os.path.isdir(repo_path):
        logger.error("Repository path does not exist: %s", repo_path)
        return "", "", []

    tree_lines: List[str] = []
    key_contents: List[str] = []
    evidence: List[str] = []
    file_count = 0

    for root, dirs, files in os.walk(repo_path):
        # --- prune ignored directories in-place ---
        dirs[:] = [
            d for d in dirs
            if d not in settings.skip_dirs
        ]

        depth = root.replace(repo_path, "").count(os.sep)
        if depth > settings.max_tree_depth:
            dirs.clear()
            continue

        indent = "  " * depth
        tree_lines.append(f"{indent}{os.path.basename(root)}/")

        for filename in files:
            file_count += 1
            if file_count > settings.max_files:
                logger.warning(
                    "Max file limit (%d) reached — truncating scan.",
                    settings.max_files,
                )
                dirs.clear()
                break

            tree_lines.append(f"{indent}  {filename}")

            if filename in settings.important_files:
                full_path = os.path.join(root, filename)
                _read_important_file(
                    full_path, filename, settings.max_file_size_bytes,
                    key_contents, evidence,
                )

    logger.info("Scanned %d files from %s", file_count, repo_path)
    return "\n".join(tree_lines), "\n".join(key_contents), evidence


def _read_important_file(
    full_path: str,
    filename: str,
    max_bytes: int,
    key_contents: List[str],
    evidence: List[str],
) -> None:
    """Safely read an important file and append to accumulators."""
    try:
        size = os.path.getsize(full_path)
        if size > max_bytes:
            logger.debug("Skipping oversized file %s (%d bytes)", full_path, size)
            return

        with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read(max_bytes)

        key_contents.append(f"\n### FILE: {filename}\n{content}")
        evidence.append(full_path)
    except OSError as exc:
        logger.debug("Could not read %s: %s", full_path, exc)

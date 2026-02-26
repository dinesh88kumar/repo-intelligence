"""
Module dependency mapper — analyses import relationships between files.

Capabilities:
- Build a module-level dependency graph from import statements
- Detect circular dependencies via DFS
- Identify high-coupling modules (high in-degree)
"""

from __future__ import annotations

import ast
import logging
import os
import re
from collections import defaultdict
from typing import Dict, List, Set, Tuple

from config.settings import ScanSettings, load_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Import extraction
# ---------------------------------------------------------------------------

def _extract_python_imports(filepath: str) -> List[str]:
    """Parse a Python file's AST to extract imported module names."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
        tree = ast.parse(source, filename=filepath)
    except (SyntaxError, OSError) as exc:
        logger.debug("Cannot parse %s: %s", filepath, exc)
        return []

    imports: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])
    return imports


_JS_IMPORT_RE = re.compile(
    r"""(?:import\s+.*?\s+from\s+['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\s*\))""",
    re.MULTILINE,
)


def _extract_js_imports(filepath: str) -> List[str]:
    """Regex-based import extraction for JavaScript / TypeScript files."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
    except OSError:
        return []

    imports: List[str] = []
    for m in _JS_IMPORT_RE.finditer(source):
        module = m.group(1) or m.group(2)
        if module:
            imports.append(module.split("/")[0])
    return imports


_JAVA_IMPORT_RE = re.compile(r"^import\s+([\w.]+);", re.MULTILINE)


def _extract_java_imports(filepath: str) -> List[str]:
    """Extract package imports from Java / Kotlin files."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
    except OSError:
        return []

    return [m.group(1).split(".")[0] for m in _JAVA_IMPORT_RE.finditer(source)]


_EXTRACTORS = {
    ".py": _extract_python_imports,
    ".js": _extract_js_imports,
    ".ts": _extract_js_imports,
    ".jsx": _extract_js_imports,
    ".tsx": _extract_js_imports,
    ".java": _extract_java_imports,
    ".kt": _extract_java_imports,
}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_dependency_graph(
    repo_path: str,
    settings: ScanSettings | None = None,
) -> Dict[str, List[str]]:
    """
    Build a mapping ``module_file -> [imported_module, ...]`` for the repo.

    Only internal (relative-looking) imports are linked; third-party
    packages are ignored to keep the graph focused on coupling.
    """
    if settings is None:
        settings = load_settings().scan

    repo_path = os.path.abspath(repo_path)
    graph: Dict[str, List[str]] = defaultdict(list)

    # Collect all source file basenames for internal-link detection
    internal_modules: Set[str] = set()
    source_files: List[Tuple[str, str]] = []  # (full_path, extension)

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in settings.skip_dirs]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in _EXTRACTORS:
                full = os.path.join(root, fname)
                source_files.append((full, ext))
                # register module name (filename without ext)
                internal_modules.add(os.path.splitext(fname)[0])
                # register directory name (package)
                rel = os.path.relpath(root, repo_path)
                if rel != ".":
                    internal_modules.add(rel.replace(os.sep, ".").split(".")[0])

    file_count = 0
    for full_path, ext in source_files:
        file_count += 1
        if file_count > settings.max_files:
            break

        extractor = _EXTRACTORS[ext]
        imports = extractor(full_path)
        rel = os.path.relpath(full_path, repo_path)

        internal_imports = [
            imp for imp in imports if imp in internal_modules
        ]
        if internal_imports:
            graph[rel] = internal_imports

    logger.info(
        "Dependency graph: %d modules, %d edges",
        len(graph),
        sum(len(v) for v in graph.values()),
    )
    return dict(graph)


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

def find_circular_dependencies(
    graph: Dict[str, List[str]],
) -> List[List[str]]:
    """
    Detect circular dependency chains via iterative DFS.

    Returns a list of cycles (each cycle is a list of module names).
    """
    visited: Set[str] = set()
    rec_stack: Set[str] = set()
    cycles: List[List[str]] = []
    path: List[str] = []

    def _dfs(node: str) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbour in graph.get(node, []):
            if neighbour not in visited:
                _dfs(neighbour)
            elif neighbour in rec_stack:
                idx = path.index(neighbour)
                cycle = path[idx:] + [neighbour]
                cycles.append(cycle)

        path.pop()
        rec_stack.discard(node)

    for node in graph:
        if node not in visited:
            _dfs(node)

    return cycles


def find_high_coupling_modules(
    graph: Dict[str, List[str]],
    threshold: int = 5,
) -> List[str]:
    """
    Return modules that are imported by more than `threshold` other modules.
    """
    in_degree: Dict[str, int] = defaultdict(int)
    for deps in graph.values():
        for dep in deps:
            in_degree[dep] += 1

    return sorted(
        [mod for mod, count in in_degree.items() if count >= threshold],
        key=lambda m: in_degree[m],
        reverse=True,
    )


def analyse_dependencies(
    repo_path: str,
    settings: ScanSettings | None = None,
) -> dict:
    """
    Full dependency analysis pipeline.

    Returns a dict matching the DependencyInfo schema in state.py.
    """
    graph = build_dependency_graph(repo_path, settings)
    circular = find_circular_dependencies(graph)
    high_coupling = find_high_coupling_modules(graph)

    return {
        "module_graph": graph,
        "circular_dependencies": circular,
        "high_coupling_modules": high_coupling,
    }

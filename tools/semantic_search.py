"""
Semantic code search using FAISS + LangChain embeddings.

Capabilities:
- Chunk source files intelligently (respecting function/class boundaries)
- Build an in-memory FAISS index
- Query top-k relevant code chunks with scores
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from config.settings import SemanticSearchSettings, ScanSettings, load_settings

logger = logging.getLogger(__name__)


@dataclass
class CodeChunk:
    """A chunk of source code with its metadata."""

    content: str
    file_path: str
    start_line: int
    end_line: int
    language: str


# ---------------------------------------------------------------------------
# File reading & chunking
# ---------------------------------------------------------------------------

_EXTENSION_TO_LANG = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".jsx": "jsx", ".tsx": "tsx", ".java": "java", ".go": "go",
    ".rs": "rust", ".rb": "ruby", ".php": "php", ".cs": "csharp",
    ".kt": "kotlin", ".scala": "scala", ".swift": "swift",
    ".c": "c", ".cpp": "cpp", ".h": "c", ".hpp": "cpp",
    ".yaml": "yaml", ".yml": "yaml", ".json": "json",
    ".toml": "toml", ".xml": "xml", ".sql": "sql",
    ".graphql": "graphql", ".proto": "protobuf", ".md": "markdown",
}


def _detect_language(filepath: str) -> str:
    """Return language identifier from file extension."""
    ext = os.path.splitext(filepath)[1].lower()
    return _EXTENSION_TO_LANG.get(ext, "text")


def _chunk_file(
    filepath: str,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
) -> List[CodeChunk]:
    """
    Split a file into overlapping chunks of roughly `chunk_size` characters.

    Chunks try to break at newlines to keep logical coherence.
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            content = fh.read()
    except OSError as exc:
        logger.debug("Cannot read %s: %s", filepath, exc)
        return []

    if not content.strip():
        return []

    language = _detect_language(filepath)
    lines = content.split("\n")
    chunks: List[CodeChunk] = []

    current_chars = 0
    start_idx = 0

    for i, line in enumerate(lines):
        current_chars += len(line) + 1  # +1 for newline
        if current_chars >= chunk_size:
            chunk_text = "\n".join(lines[start_idx : i + 1])
            chunks.append(CodeChunk(
                content=chunk_text,
                file_path=filepath,
                start_line=start_idx + 1,
                end_line=i + 1,
                language=language,
            ))
            # slide window with overlap
            overlap_lines = max(1, chunk_overlap // 80)
            start_idx = max(start_idx + 1, i + 1 - overlap_lines)
            current_chars = sum(len(lines[j]) + 1 for j in range(start_idx, i + 1))

    # remaining lines
    if start_idx < len(lines):
        chunk_text = "\n".join(lines[start_idx:])
        if chunk_text.strip():
            chunks.append(CodeChunk(
                content=chunk_text,
                file_path=filepath,
                start_line=start_idx + 1,
                end_line=len(lines),
                language=language,
            ))

    return chunks


# ---------------------------------------------------------------------------
# Index building & querying
# ---------------------------------------------------------------------------

class SemanticIndex:
    """
    In-memory FAISS index over code chunks.

    Uses langchain_community FAISS vectorstore with HuggingFace embeddings
    (runs locally — no API keys needed).
    """

    def __init__(
        self,
        search_settings: Optional[SemanticSearchSettings] = None,
        scan_settings: Optional[ScanSettings] = None,
    ) -> None:
        settings = load_settings()
        self._search = search_settings or settings.search
        self._scan = scan_settings or settings.scan
        self._chunks: List[CodeChunk] = []
        self._vectorstore = None  # Lazy init

    # ----- build -----

    def build_from_repo(self, repo_path: str) -> int:
        """
        Walk the repo, chunk all code files, and build a FAISS index.

        Returns the total number of chunks indexed.
        """
        repo_path = os.path.abspath(repo_path)
        self._chunks = []
        file_count = 0

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in self._scan.skip_dirs]

            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in self._search.code_extensions:
                    continue

                full_path = os.path.join(root, fname)
                try:
                    if os.path.getsize(full_path) > self._scan.max_file_size_bytes:
                        continue
                except OSError:
                    continue

                file_count += 1
                if file_count > self._scan.max_files:
                    logger.warning("Semantic index: file limit reached, stopping.")
                    break

                self._chunks.extend(
                    _chunk_file(
                        full_path,
                        chunk_size=self._search.chunk_size,
                        chunk_overlap=self._search.chunk_overlap,
                    )
                )

        if not self._chunks:
            logger.warning("No code chunks found in %s", repo_path)
            return 0

        self._build_vectorstore()
        logger.info(
            "Semantic index built: %d chunks from %d files",
            len(self._chunks),
            file_count,
        )
        return len(self._chunks)

    def _build_vectorstore(self) -> None:
        """Construct the FAISS vectorstore from collected chunks."""
        from langchain_community.vectorstores import FAISS
        from langchain_huggingface import HuggingFaceEmbeddings

        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
        )

        texts = [c.content for c in self._chunks]
        metadatas = [
            {
                "file_path": c.file_path,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "language": c.language,
            }
            for c in self._chunks
        ]

        self._vectorstore = FAISS.from_texts(
            texts, embeddings, metadatas=metadatas,
        )

    # ----- query -----

    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
    ) -> List[Tuple[str, dict, float]]:
        """
        Search the index for chunks relevant to `question`.

        Returns list of (content, metadata, score) sorted by relevance.
        """
        if self._vectorstore is None:
            logger.warning("Semantic index not built yet.")
            return []

        k = top_k or self._search.top_k
        results = self._vectorstore.similarity_search_with_score(question, k=k)

        return [
            (doc.page_content, doc.metadata, score)
            for doc, score in results
        ]

    def query_formatted(
        self,
        question: str,
        top_k: Optional[int] = None,
    ) -> str:
        """Return query results as a formatted string for LLM prompts."""
        results = self.query(question, top_k)
        if not results:
            return "No relevant code found."

        parts: List[str] = []
        for i, (content, meta, score) in enumerate(results, 1):
            parts.append(
                f"### Chunk {i} — {meta['file_path']}  "
                f"(lines {meta['start_line']}-{meta['end_line']}, "
                f"score={score:.3f})\n```{meta['language']}\n{content}\n```"
            )
        return "\n\n".join(parts)

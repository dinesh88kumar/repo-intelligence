"""
FastAPI endpoint for the Repository Intelligence System.

Usage:
    uv run uvicorn api.main:app --reload

Endpoints:
    POST /analyze-repo  — Analyse a repository and return the full report.
    GET  /health        — Health check.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from config.settings import load_settings
from graph.workflow import build_graph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("repo-intelligence-api")

app = FastAPI(
    title="Repository Intelligence API",
    description="AI-powered repository analysis and best-practices assessment.",
    version="2.0.0",
)


class AnalyzeRequest(BaseModel):
    """Request body for /analyze-repo."""

    repo_path: str = Field(..., description="Path to the repository to analyse.")
    model: Optional[str] = Field(None, description="Override LLM model name.")


class AnalyzeResponse(BaseModel):
    """Response body for /analyze-repo."""

    report: str
    maturity_score: int
    elapsed_seconds: float


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "repo-intelligence"}


@app.post("/analyze-repo", response_model=AnalyzeResponse)
async def analyze_repo(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Analyse a repository and return the full intelligence report.

    This runs synchronously because LLM inference is CPU-bound.
    For production, consider wrapping in a task queue (Celery, etc.).
    """
    try:
        from langchain_ollama.llms import OllamaLLM

        settings = load_settings()
        model_name = request.model or settings.llm.model_name

        llm = OllamaLLM(model=model_name)
        pipeline = build_graph(llm)

        initial_state = {
            "repo_path": request.repo_path,
            "repo_tree": "",
            "key_files": "",
            "tech_stack": "",
            "business_summary": "",
            "evidence": [],
            "final_report": "",
            "entities": {},
            "workflows": {},
            "business_context": {},
            "architecture": {},
            "complexity_metrics": {},
            "dependencies": {},
            "gap_analysis": {},
            "errors": [],
        }

        start = time.time()
        result = pipeline.invoke(initial_state)
        elapsed = time.time() - start

        gap = result.get("gap_analysis", {})

        return AnalyzeResponse(
            report=result.get("final_report", "No report generated."),
            maturity_score=gap.get("maturity_score", 0),
            elapsed_seconds=round(elapsed, 1),
        )

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Repository not found: {request.repo_path}")
    except Exception as exc:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))

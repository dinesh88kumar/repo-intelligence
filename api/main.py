"""
FastAPI endpoint for the Repository Intelligence System.

Usage:
    uv run uvicorn api.main:app --reload

Endpoints:
    POST /analyze-repo      — Analyse a local repository.
    POST /analyze-github     — Clone a public GitHub repo, analyse, and clean up.
    GET  /health             — Health check.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
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

# ── CORS ──────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Serve frontend ───────────────────────────────────────
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="frontend")


# ── Request / Response models ────────────────────────────
class AnalyzeRequest(BaseModel):
    """Request body for /analyze-repo."""
    repo_path: str = Field(..., description="Path to the repository to analyse.")
    model: Optional[str] = Field(None, description="Override LLM model name.")


class GitHubAnalyzeRequest(BaseModel):
    """Request body for /analyze-github."""
    github_url: str = Field(..., description="Public GitHub repository URL.")
    model: Optional[str] = Field(None, description="Override LLM model name.")


class AnalyzeResponse(BaseModel):
    """Response body for /analyze-repo."""
    report: str
    maturity_score: int
    elapsed_seconds: float
    architecture: Dict[str, Any] = {}
    business_context: Dict[str, Any] = {}
    entities: Dict[str, Any] = {}
    workflows: Dict[str, Any] = {}
    complexity_metrics: Dict[str, Any] = {}
    dependencies: Dict[str, Any] = {}
    gap_analysis: Dict[str, Any] = {}
    tech_stack: str = ""


# ── In-memory job tracking for SSE ───────────────────────
_jobs: Dict[str, Dict[str, Any]] = {}


# ── Health ────────────────────────────────────────────────
@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "repo-intelligence"}


# ── Serve the frontend ────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main UI."""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.isfile(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Frontend not found</h1>", status_code=404)


# ── Local repo analysis ──────────────────────────────────
@app.post("/analyze-repo", response_model=AnalyzeResponse)
async def analyze_repo(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyse a local repository and return the full intelligence report."""
    try:
        from config.llm_factory import create_llm

        settings = load_settings()
        llm = create_llm(settings, model_override=request.model)
        pipeline = build_graph(llm)

        initial_state = _build_initial_state(request.repo_path)

        start = time.time()
        result = pipeline.invoke(initial_state)
        elapsed = time.time() - start

        return _build_response(result, elapsed)

    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Repository not found: {request.repo_path}")
    except Exception as exc:
        logger.exception("Analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ── GitHub repo analysis (SSE streaming) ─────────────────
@app.post("/analyze-github")
async def analyze_github(request: GitHubAnalyzeRequest):
    """
    Clone a public GitHub repo, analyse it, and clean up.
    Returns results via Server-Sent Events for real-time UI updates.
    """
    url = request.github_url.strip()
    if not _validate_github_url(url):
        raise HTTPException(status_code=400, detail="Invalid GitHub URL. Provide a public repository URL.")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "queued", "events": [], "result": None}

    # Run analysis in background
    asyncio.create_task(_run_github_analysis(job_id, url, request.model))

    return {"job_id": job_id}


@app.get("/analyze-github/stream/{job_id}")
async def stream_analysis(job_id: str):
    """SSE stream for a running analysis job."""
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        last_idx = 0
        while True:
            job = _jobs.get(job_id)
            if not job:
                break

            # Send any new events
            events = job["events"]
            while last_idx < len(events):
                yield f"data: {json.dumps(events[last_idx])}\n\n"
                last_idx += 1

            if job["status"] in ("done", "error"):
                break

            await asyncio.sleep(0.5)

        # Clean up
        if job_id in _jobs:
            del _jobs[job_id]

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Sync GitHub analysis (non-streaming fallback) ────────
@app.post("/analyze-github/sync", response_model=AnalyzeResponse)
async def analyze_github_sync(request: GitHubAnalyzeRequest) -> AnalyzeResponse:
    """Clone, analyse, and return results in a single request (no streaming)."""
    url = request.github_url.strip()
    if not _validate_github_url(url):
        raise HTTPException(status_code=400, detail="Invalid GitHub URL.")

    tmp_dir = tempfile.mkdtemp(prefix="repo_intel_")
    try:
        # Clone
        _emit_log(None, "clone", f"Cloning {url}...")
        clone_path = _clone_repo(url, tmp_dir)

        # Analyse
        from config.llm_factory import create_llm
        settings = load_settings()
        llm = create_llm(settings, model_override=request.model)
        pipeline = build_graph(llm)

        initial_state = _build_initial_state(clone_path)
        start = time.time()
        result = pipeline.invoke(initial_state)
        elapsed = time.time() - start

        return _build_response(result, elapsed)
    except Exception as exc:
        logger.exception("GitHub analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Helpers ──────────────────────────────────────────────
def _validate_github_url(url: str) -> bool:
    """Basic validation for GitHub URLs."""
    return (
        url.startswith("https://github.com/")
        and len(url.split("/")) >= 5
    )


def _clone_repo(url: str, parent_dir: str) -> str:
    """Clone a GitHub repo into parent_dir and return the clone path."""
    # Extract repo name from URL
    repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
    clone_path = os.path.join(parent_dir, repo_name)

    result = subprocess.run(
        ["git", "clone", "--depth", "1", url, clone_path],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Git clone failed: {result.stderr}")

    return clone_path


def _build_initial_state(repo_path: str) -> Dict[str, Any]:
    """Construct the initial pipeline state."""
    return {
        "repo_path": repo_path,
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


def _build_response(result: Dict[str, Any], elapsed: float) -> AnalyzeResponse:
    """Build AnalyzeResponse from pipeline result."""
    gap = result.get("gap_analysis", {})
    return AnalyzeResponse(
        report=result.get("final_report", "No report generated."),
        maturity_score=gap.get("maturity_score", 0),
        elapsed_seconds=round(elapsed, 1),
        architecture=result.get("architecture", {}),
        business_context=result.get("business_context", {}),
        entities=result.get("entities", {}),
        workflows=result.get("workflows", {}),
        complexity_metrics=result.get("complexity_metrics", {}),
        dependencies=result.get("dependencies", {}),
        gap_analysis=result.get("gap_analysis", {}),
        tech_stack=result.get("tech_stack", ""),
    )


def _emit_log(job_id: Optional[str], step: str, message: str, **kwargs):
    """Emit a progress event for a job."""
    event = {"step": step, "message": message, **kwargs}
    logger.info("[%s] %s: %s", job_id or "sync", step, message)
    if job_id and job_id in _jobs:
        _jobs[job_id]["events"].append(event)


async def _run_github_analysis(job_id: str, url: str, model_override: Optional[str]):
    """Background task: clone → analyse → clean up → emit results via SSE."""
    tmp_dir = tempfile.mkdtemp(prefix="repo_intel_")
    try:
        _jobs[job_id]["status"] = "running"

        # Step 1: Clone
        _emit_log(job_id, "clone", f"Cloning repository...", progress=5)
        clone_path = await asyncio.to_thread(_clone_repo, url, tmp_dir)
        _emit_log(job_id, "clone_done", "Repository cloned successfully.", progress=10)

        # Step 2: Run analysis pipeline
        from config.llm_factory import create_llm

        settings = load_settings()
        llm = create_llm(settings, model_override=model_override)
        pipeline = build_graph(llm)
        initial_state = _build_initial_state(clone_path)

        _emit_log(job_id, "analyzing", "Starting analysis pipeline...", progress=15)

        start = time.time()

        # Stream pipeline execution
        def _run_pipeline():
            results = {}
            step_progress = {
                "scan_repo": 25,
                "extract_entities": 40,
                "analyse_workflows": 50,
                "business_context": 60,
                "analyse_architecture": 75,
                "gap_analysis": 85,
                "generate_report": 95,
            }
            for step_output in pipeline.stream(initial_state):
                for node_name, node_state in step_output.items():
                    results.update(node_state)
                    progress = step_progress.get(node_name, 50)
                    _emit_log(
                        job_id, node_name,
                        f"Completed: {node_name.replace('_', ' ').title()}",
                        progress=progress,
                        data=_safe_serialize(node_state),
                    )
            return results

        result = await asyncio.to_thread(_run_pipeline)
        elapsed = time.time() - start

        # Step 3: Clean up
        _emit_log(job_id, "cleanup", "Cleaning up temporary files...", progress=98)
        shutil.rmtree(tmp_dir, ignore_errors=True)

        # Step 4: Emit final result
        response = _build_response(result, elapsed)
        _emit_log(
            job_id, "complete",
            f"Analysis completed in {elapsed:.1f}s",
            progress=100,
            result=response.model_dump(),
        )
        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["result"] = response.model_dump()

    except Exception as exc:
        logger.exception("GitHub analysis failed for job %s", job_id)
        _emit_log(job_id, "error", str(exc), progress=0)
        _jobs[job_id]["status"] = "error"
        # Clean up on error too
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _safe_serialize(obj: Any) -> Any:
    """Ensure the object is JSON-serializable."""
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)

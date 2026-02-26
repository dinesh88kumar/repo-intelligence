"""
Shared state schema for the Repository Intelligence LangGraph pipeline.

Every field used by any agent MUST be declared here so LangGraph preserves it.
Phase-1 fields are preserved; new phases add to the schema additively.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class EntityInfo(TypedDict, total=False):
    """Structured representation of extracted domain entities."""

    domain_entities: List[str]
    api_endpoints: List[str]
    database_models: List[str]
    external_integrations: List[str]


class WorkflowInfo(TypedDict, total=False):
    """Structured representation of inferred workflows."""

    primary_flows: List[str]
    request_paths: List[str]
    background_jobs: List[str]
    evidence_files: List[str]


class BusinessContext(TypedDict, total=False):
    """Structured business context output."""

    domain: str
    primary_users: List[str]
    core_features: List[str]
    business_workflows: List[str]
    confidence_score: float


class ArchitectureInfo(TypedDict, total=False):
    """Detected architecture patterns."""

    pattern: str  # monolith / microservices / modular-monolith
    layers: List[str]
    api_style: str  # REST / GraphQL / gRPC / mixed
    auth_mechanism: str
    database_type: str
    evidence: List[str]


class ComplexityMetrics(TypedDict, total=False):
    """Repository complexity measurements."""

    total_files: int
    total_loc: int
    service_count: int
    test_coverage_heuristic: str
    languages: Dict[str, int]


class DependencyInfo(TypedDict, total=False):
    """Module dependency analysis results."""

    module_graph: Dict[str, List[str]]
    circular_dependencies: List[List[str]]
    high_coupling_modules: List[str]


class GapAnalysis(TypedDict, total=False):
    """Best-practices gap analysis results."""

    strengths: List[str]
    gaps: List[str]
    risks: List[str]
    recommendations: List[str]
    maturity_score: int  # 0-100
    security_issues: List[str]


class AgentState(TypedDict, total=False):
    """
    Master state flowing through the LangGraph pipeline.

    Using `total=False` so agents only need to return the keys they set.
    Phase-1 keys are preserved; phases 2-5 add new keys additively.
    """

    # ── Phase 1 (existing) ────────────────────────────────
    repo_path: str
    repo_tree: str
    key_files: str
    tech_stack: str
    business_summary: str
    evidence: List[str]
    final_report: str

    # ── Phase 2 — Deep Business Context ───────────────────
    entities: EntityInfo
    workflows: WorkflowInfo
    business_context: BusinessContext

    # ── Phase 3 — Architecture Intelligence ───────────────
    architecture: ArchitectureInfo
    complexity_metrics: ComplexityMetrics
    dependencies: DependencyInfo

    # ── Phase 4 — Best Practices ──────────────────────────
    gap_analysis: GapAnalysis

    # ── Internal / config ─────────────────────────────────
    errors: List[str]

"""
Best-practices rule engine for repository assessment.

Each rule set is a list of Rule objects that can be evaluated against
the repository state. Rules produce findings with severity levels.

Supported frameworks: FastAPI, Spring Boot, Node/Express, General Backend.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    """Rule severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Finding:
    """A single finding produced by evaluating a rule."""
    rule_name: str
    description: str
    severity: Severity
    passed: bool
    evidence: str = ""
    recommendation: str = ""


@dataclass
class Rule:
    """
    A best-practice rule with detection logic.

    The `check` callable receives (repo_path, key_files_content, tech_stack)
    and returns a Finding.
    """
    name: str
    description: str
    severity: Severity
    category: str
    check: Callable[..., Finding]
    frameworks: List[str] = field(default_factory=lambda: ["general"])


# ---------------------------------------------------------------------------
# Helper scanners
# ---------------------------------------------------------------------------

def _file_contains(repo_path: str, pattern: str, extensions: tuple[str, ...] = (".py", ".js", ".ts", ".java")) -> List[str]:
    """Search for a regex pattern in source files. Returns matching file paths."""
    matches: List[str] = []
    regex = re.compile(pattern, re.IGNORECASE)
    skip = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

    file_count = 0
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in skip]
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in extensions:
                continue
            file_count += 1
            if file_count > 2000:
                return matches
            full = os.path.join(root, fname)
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read(200_000)
                if regex.search(content):
                    matches.append(os.path.relpath(full, repo_path))
            except OSError:
                pass
    return matches


def _file_exists(repo_path: str, names: List[str]) -> Optional[str]:
    """Return the first filename found in the repo root, or None."""
    for name in names:
        if os.path.isfile(os.path.join(repo_path, name)):
            return name
    return None


def _has_directory(repo_path: str, names: List[str]) -> Optional[str]:
    """Return the first directory found in the repo root, or None."""
    for name in names:
        if os.path.isdir(os.path.join(repo_path, name)):
            return name
    return None


# ---------------------------------------------------------------------------
# Rule definitions — General Backend
# ---------------------------------------------------------------------------

def _check_env_files(repo_path: str, key_files: str, tech_stack: str) -> Finding:
    """Check that .env is gitignored and .env.example exists."""
    gitignore_path = os.path.join(repo_path, ".gitignore")
    env_in_gitignore = False
    if os.path.isfile(gitignore_path):
        try:
            with open(gitignore_path, "r", encoding="utf-8") as fh:
                env_in_gitignore = ".env" in fh.read()
        except OSError:
            pass

    has_example = _file_exists(repo_path, [".env.example", ".env.sample", "env.example"])
    has_env = _file_exists(repo_path, [".env"])

    if has_env and not env_in_gitignore:
        return Finding(
            rule_name="env-files",
            description=".env file exists but is not in .gitignore",
            severity=Severity.CRITICAL,
            passed=False,
            evidence=".env, .gitignore",
            recommendation="Add `.env` to .gitignore immediately to prevent secret leaks.",
        )

    if not has_example and has_env:
        return Finding(
            rule_name="env-files",
            description=".env exists but no .env.example template provided",
            severity=Severity.MEDIUM,
            passed=False,
            evidence=".env",
            recommendation="Create a `.env.example` so collaborators know required variables.",
        )

    return Finding(
        rule_name="env-files",
        description="Environment file handling looks correct",
        severity=Severity.INFO,
        passed=True,
    )


def _check_readme(repo_path: str, key_files: str, tech_stack: str) -> Finding:
    """Check for a meaningful README."""
    readme = _file_exists(repo_path, ["README.md", "readme.md", "README.rst", "README.txt"])
    if not readme:
        return Finding(
            rule_name="readme",
            description="No README found",
            severity=Severity.HIGH,
            passed=False,
            recommendation="Add a README with project description, setup, and usage instructions.",
        )

    full = os.path.join(repo_path, readme)
    try:
        size = os.path.getsize(full)
    except OSError:
        size = 0

    if size < 100:
        return Finding(
            rule_name="readme",
            description="README exists but is very short",
            severity=Severity.MEDIUM,
            passed=False,
            evidence=readme,
            recommendation="Expand README with setup instructions, architecture overview, and usage examples.",
        )

    return Finding(
        rule_name="readme",
        description="README is present and has meaningful content",
        severity=Severity.INFO,
        passed=True,
        evidence=readme,
    )


def _check_tests(repo_path: str, key_files: str, tech_stack: str) -> Finding:
    """Check if a test directory or test files exist."""
    test_dir = _has_directory(repo_path, ["tests", "test", "__tests__", "spec"])
    test_files = _file_contains(repo_path, r"(def test_|it\(|describe\(|@Test)", (".py", ".js", ".ts", ".java"))

    if test_dir or test_files:
        return Finding(
            rule_name="tests",
            description=f"Tests found ({len(test_files)} file(s) with test patterns)",
            severity=Severity.INFO,
            passed=True,
            evidence=test_dir or ", ".join(test_files[:5]),
        )

    return Finding(
        rule_name="tests",
        description="No test files or test directory found",
        severity=Severity.HIGH,
        passed=False,
        recommendation="Add unit tests. Consider pytest (Python), Jest (JS), or JUnit (Java).",
    )


def _check_dockerfile(repo_path: str, key_files: str, tech_stack: str) -> Finding:
    """Check for containerization support."""
    docker = _file_exists(repo_path, ["Dockerfile", "docker-compose.yml", "docker-compose.yaml"])
    if docker:
        return Finding(
            rule_name="containerization",
            description="Docker configuration found",
            severity=Severity.INFO,
            passed=True,
            evidence=docker,
        )
    return Finding(
        rule_name="containerization",
        description="No Dockerfile or docker-compose found",
        severity=Severity.LOW,
        passed=False,
        recommendation="Consider adding Docker support for consistent deployments.",
    )


def _check_linting(repo_path: str, key_files: str, tech_stack: str) -> Finding:
    """Check for linting / formatting configuration."""
    lint_files = [
        ".flake8", ".pylintrc", "pyproject.toml", "setup.cfg",
        ".eslintrc.js", ".eslintrc.json", ".eslintrc.yml",
        ".prettierrc", ".prettierrc.json", "biome.json",
        "checkstyle.xml",
    ]
    found = _file_exists(repo_path, lint_files)

    if found:
        # Extra check: for pyproject.toml, see if it has linting config
        if found == "pyproject.toml":
            try:
                with open(os.path.join(repo_path, found), "r") as fh:
                    content = fh.read()
                if "ruff" in content or "flake8" in content or "pylint" in content or "black" in content:
                    return Finding(
                        rule_name="linting", description="Linting configuration found in pyproject.toml",
                        severity=Severity.INFO, passed=True, evidence=found,
                    )
            except OSError:
                pass
        else:
            return Finding(
                rule_name="linting", description="Linting configuration found",
                severity=Severity.INFO, passed=True, evidence=found,
            )

    return Finding(
        rule_name="linting",
        description="No linting / formatting configuration detected",
        severity=Severity.MEDIUM,
        passed=False,
        recommendation="Add a linter (ruff, eslint) and formatter (black, prettier) for code quality.",
    )


def _check_ci(repo_path: str, key_files: str, tech_stack: str) -> Finding:
    """Check for CI/CD configuration."""
    ci_indicators = [
        ".github/workflows",
        ".gitlab-ci.yml",
        "Jenkinsfile",
        ".circleci",
        ".travis.yml",
        "azure-pipelines.yml",
        "bitbucket-pipelines.yml",
    ]
    for indicator in ci_indicators:
        full = os.path.join(repo_path, indicator)
        if os.path.exists(full):
            return Finding(
                rule_name="ci-cd", description="CI/CD configuration found",
                severity=Severity.INFO, passed=True, evidence=indicator,
            )

    return Finding(
        rule_name="ci-cd",
        description="No CI/CD pipeline configuration found",
        severity=Severity.HIGH,
        passed=False,
        recommendation="Add a CI pipeline (GitHub Actions, GitLab CI) for automated testing and deployment.",
    )


# ---------------------------------------------------------------------------
# Security heuristics
# ---------------------------------------------------------------------------

def _check_hardcoded_secrets(repo_path: str, key_files: str, tech_stack: str) -> Finding:
    """Detect potential hardcoded secrets or API keys."""
    secret_patterns = (
        r"""(?:password|secret|api_key|apikey|access_token|private_key)\s*[=:]\s*['"][^'"]{8,}['"]"""
    )
    matches = _file_contains(repo_path, secret_patterns, (".py", ".js", ".ts", ".java", ".yaml", ".yml", ".json", ".env"))
    if matches:
        return Finding(
            rule_name="hardcoded-secrets",
            description=f"Potential hardcoded secrets found in {len(matches)} file(s)",
            severity=Severity.CRITICAL,
            passed=False,
            evidence=", ".join(matches[:5]),
            recommendation="Move secrets to environment variables or a vault; never commit them.",
        )
    return Finding(
        rule_name="hardcoded-secrets",
        description="No obvious hardcoded secrets detected",
        severity=Severity.INFO,
        passed=True,
    )


def _check_cors(repo_path: str, key_files: str, tech_stack: str) -> Finding:
    """Check for overly permissive CORS configuration."""
    cors_patterns = r"""(?:allow_origins\s*=\s*\[?\s*['"]\*['"]\]?|cors\(\s*\{?\s*origin:\s*['"]\*['"])"""
    matches = _file_contains(repo_path, cors_patterns)
    if matches:
        return Finding(
            rule_name="open-cors",
            description="CORS configured to allow all origins (*)",
            severity=Severity.HIGH,
            passed=False,
            evidence=", ".join(matches[:3]),
            recommendation="Restrict CORS to known frontend domains.",
        )
    return Finding(
        rule_name="open-cors",
        description="No overly permissive CORS configuration detected",
        severity=Severity.INFO,
        passed=True,
    )


def _check_input_validation(repo_path: str, key_files: str, tech_stack: str) -> Finding:
    """Heuristic check for input validation patterns."""
    validation_patterns = r"(?:Pydantic|BaseModel|@validator|@field_validator|Joi\.|yup\.|zod\.|@Valid|@NotNull)"
    matches = _file_contains(repo_path, validation_patterns)
    if matches:
        return Finding(
            rule_name="input-validation",
            description="Input validation patterns detected",
            severity=Severity.INFO,
            passed=True,
            evidence=", ".join(matches[:5]),
        )
    return Finding(
        rule_name="input-validation",
        description="No input validation framework detected",
        severity=Severity.MEDIUM,
        passed=False,
        recommendation="Add request validation (Pydantic, Joi, Zod) to prevent injection attacks.",
    )


def _check_auth(repo_path: str, key_files: str, tech_stack: str) -> Finding:
    """Heuristic check for authentication setup."""
    auth_patterns = r"(?:JWT|OAuth|Bearer|Depends\(.*auth|passport\.use|@PreAuthorize|SecurityContext|bcrypt|argon2)"
    matches = _file_contains(repo_path, auth_patterns)
    if matches:
        return Finding(
            rule_name="authentication",
            description="Authentication patterns detected",
            severity=Severity.INFO,
            passed=True,
            evidence=", ".join(matches[:5]),
        )
    return Finding(
        rule_name="authentication",
        description="No authentication/authorization patterns detected",
        severity=Severity.HIGH,
        passed=False,
        recommendation="Implement authentication (JWT, OAuth2) for protected endpoints.",
    )


# ---------------------------------------------------------------------------
# Framework-specific rules: FastAPI
# ---------------------------------------------------------------------------

def _check_fastapi_exception_handlers(repo_path: str, key_files: str, tech_stack: str) -> Finding:
    matches = _file_contains(repo_path, r"@app\.exception_handler|HTTPException")
    if matches:
        return Finding("fastapi-error-handling", "FastAPI error handling found", Severity.INFO, True, ", ".join(matches[:3]))
    return Finding(
        "fastapi-error-handling", "No custom exception handlers found",
        Severity.MEDIUM, False, recommendation="Add @app.exception_handler for consistent error responses.",
    )


def _check_fastapi_response_models(repo_path: str, key_files: str, tech_stack: str) -> Finding:
    matches = _file_contains(repo_path, r"response_model\s*=")
    if matches:
        return Finding("fastapi-response-models", "Response models used in endpoints", Severity.INFO, True, ", ".join(matches[:3]))
    return Finding(
        "fastapi-response-models", "No response_model declarations found on endpoints",
        Severity.MEDIUM, False, recommendation="Use response_model in route decorators for auto-documentation and serialization.",
    )


# ---------------------------------------------------------------------------
# Framework-specific rules: Node/Express
# ---------------------------------------------------------------------------

def _check_helmet(repo_path: str, key_files: str, tech_stack: str) -> Finding:
    matches = _file_contains(repo_path, r"require\(['\"]helmet['\"]\)|import.*helmet", (".js", ".ts"))
    if matches:
        return Finding("express-helmet", "Helmet.js is used for security headers", Severity.INFO, True, ", ".join(matches[:3]))
    return Finding(
        "express-helmet", "Helmet.js not detected",
        Severity.MEDIUM, False, recommendation="Add `helmet` middleware for secure HTTP headers.",
    )


def _check_rate_limiting(repo_path: str, key_files: str, tech_stack: str) -> Finding:
    matches = _file_contains(repo_path, r"rate.?limit|express-rate-limit|slowapi|throttle", (".py", ".js", ".ts", ".java"))
    if matches:
        return Finding("rate-limiting", "Rate limiting detected", Severity.INFO, True, ", ".join(matches[:3]))
    return Finding(
        "rate-limiting", "No rate limiting detected",
        Severity.MEDIUM, False, recommendation="Add rate limiting to protect against abuse (slowapi for FastAPI, express-rate-limit for Express).",
    )


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------

GENERAL_RULES: List[Rule] = [
    Rule("env-files", "Environment file management", Severity.CRITICAL, "security", _check_env_files),
    Rule("readme", "README documentation", Severity.HIGH, "documentation", _check_readme),
    Rule("tests", "Test coverage", Severity.HIGH, "testing", _check_tests),
    Rule("containerization", "Docker support", Severity.LOW, "devops", _check_dockerfile),
    Rule("linting", "Code linting/formatting", Severity.MEDIUM, "quality", _check_linting),
    Rule("ci-cd", "CI/CD pipeline", Severity.HIGH, "devops", _check_ci),
    Rule("hardcoded-secrets", "Hardcoded secrets", Severity.CRITICAL, "security", _check_hardcoded_secrets),
    Rule("open-cors", "CORS configuration", Severity.HIGH, "security", _check_cors),
    Rule("input-validation", "Input validation", Severity.MEDIUM, "security", _check_input_validation),
    Rule("authentication", "Authentication mechanism", Severity.HIGH, "security", _check_auth),
    Rule("rate-limiting", "Rate limiting", Severity.MEDIUM, "security", _check_rate_limiting),
]

FASTAPI_RULES: List[Rule] = [
    Rule("fastapi-error-handling", "FastAPI exception handlers", Severity.MEDIUM, "quality", _check_fastapi_exception_handlers, ["fastapi"]),
    Rule("fastapi-response-models", "FastAPI response models", Severity.MEDIUM, "quality", _check_fastapi_response_models, ["fastapi"]),
]

EXPRESS_RULES: List[Rule] = [
    Rule("express-helmet", "Helmet.js security headers", Severity.MEDIUM, "security", _check_helmet, ["express"]),
]


def get_rules_for_stack(tech_stack: str) -> List[Rule]:
    """Return applicable rules based on detected tech stack string."""
    rules = list(GENERAL_RULES)
    tech_lower = tech_stack.lower()

    if "fastapi" in tech_lower:
        rules.extend(FASTAPI_RULES)
    if "express" in tech_lower or "node" in tech_lower:
        rules.extend(EXPRESS_RULES)

    return rules


def evaluate_rules(
    repo_path: str,
    key_files: str,
    tech_stack: str,
    rules: List[Rule] | None = None,
) -> List[Finding]:
    """
    Evaluate all applicable rules against the repository.

    Returns a list of Finding objects.
    """
    if rules is None:
        rules = get_rules_for_stack(tech_stack)

    findings: List[Finding] = []
    for rule in rules:
        try:
            finding = rule.check(repo_path, key_files, tech_stack)
            findings.append(finding)
        except Exception as exc:
            logger.warning("Rule %s failed: %s", rule.name, exc)
            findings.append(Finding(
                rule_name=rule.name,
                description=f"Rule evaluation failed: {exc}",
                severity=rule.severity,
                passed=False,
            ))

    return findings

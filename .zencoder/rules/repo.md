---
description: Repository Information Overview
alwaysApply: true
---

# repo-intelligence Information

## Summary
`repo-intelligence` is a minimal Python project initialized with `pyproject.toml`. It serves as a repository intelligence utility, currently featuring a simple "Hello from repo-intelligence!" implementation.

## Structure
- **Root**: Contains the main application script and configuration files.
- **.zencoder/**: Workspace-specific configuration and workflows for Zencoder.
- **.zenflow/**: Workspace-specific configuration and workflows for Zenflow.

## Language & Runtime
**Language**: Python  
**Version**: 3.12 (specified in `.python-version` and `pyproject.toml`)  
**Build System**: `pyproject.toml` (standard Python build system)  
**Package Manager**: `uv` or `pip`

## Dependencies
**Main Dependencies**:
- No external dependencies are currently specified in `pyproject.toml`.

## Build & Installation
```bash
# Using pip
pip install -e .

# Using uv (recommended)
uv sync
```

## Main Files & Resources
- **main.py**: The primary entry point for the application.
- **pyproject.toml**: Central project configuration, including metadata and dependency declarations.
- **.python-version**: Local Python version specification for tools like `pyenv` or `uv`.

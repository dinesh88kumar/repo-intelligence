# Repository Intelligence System 🧠

An AI-powered, modular system that deeply analyzes source code repositories to extract business context, detect architectural patterns, map dependencies, and evaluate against industry best practices.

Built with **Python**, **LangGraph**, **LangChain**, and **Ollama** (Local LLMs).

---

## 🌟 Features

*   **Deep Business Context (Phase 2):** Uses semantic search (FAISS + embeddings) to chunk large files, extract domain entities (Users, Orders), API endpoints, database models, and infer application workflows directly from the codebase.
*   **Architecture Intelligence (Phase 3):** Automatically detects architectural patterns (e.g., Microservices vs. Monolith), API styles (REST/GraphQL), calculates complexity metrics (LOC, test coverage), and maps recursive file dependency loops.
*   **Best Practices Gap Analysis (Phase 4):** A deterministic rule engine that runs checks against your repository for missing linting, CI/CD configurations, hardcoded secrets, open CORS, rate-limiting, and FastAPI/Express-specific flaws — converting findings into a 0-100 Maturity Score.
*   **Executive Reporting (Phase 5):** Aggregates the pipeline output into a comprehensive Markdown report featuring Risk Heatmaps (🔴/🟡/🟢 metrics) and prioritized recommendations. 
*   **FastAPI & CLI ready:** Run scans locally via terminal streaming or launch the FastAPI server to accept cross-platform REST payloads.

---

## 🛠️ Architecture

Pipeline orchestrations are driven by a 7-node **LangGraph** `StateGraph`, maintaining a carefully typed schema definition throughout execution:
1. `scan_repo` (Builds file trees & detects tech stack)
2. `extract_entities` (Semantic entity generation)
3. `analyse_workflows` (Identifies paths and back-ground jobs)
4. `business_context` (Generates structured business intent)
5. `analyse_architecture` (Complexity metrics & architectural patterns)
6. `gap_analysis` (Runs deterministic rule checks)
7. `generate_report` (Assembles Markdown output)

---

## 🚀 Installation & Setup

Ensure you have [uv](https://github.com/astral-sh/uv) installed to manage the Python environment.

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd repo_intelligence
   ```

2. **Sync Dependencies:**
   Install required packages (FastAPI, LangChain, FAISS, Sentence Transformers).
   ```bash
   uv sync
   ```

3. **Install Ollama:**
   Ensure you have [Ollama](https://ollama.com/) running locally. The system defaults to using the `qwen3:4b` model. Pull the model before running:
   ```bash
   ollama run qwen3:4b
   ```

---

## 💻 Usage

### 1. CLI (Command Line Interface)

The best way to run the system with real-time feedback.

**Run a streaming analysis (Recommended for large repos):**
```bash
uv run python main.py /path/to/target/repository --stream
```

**Run ans save the report to a file:**
```bash
uv run python main.py /path/to/target/repository --output my_report.md
```

**Override the default LLM model via CLI:**
```bash
uv run python main.py /path/to/target/repository --model llama3.1
```

### 2. API Server (FastAPI)

Launch the backend to serve reports over HTTP:

```bash
uv run uvicorn api.main:app --reload
```

Send a generic POST request to begin analysis:
```bash
curl -X POST http://127.0.0.1:8000/analyze-repo \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "./sample_applications/shop_app"}'
```

---

## ⚙️ Configuration

Tuning parameters are centralized within `config/settings.py`. You can override core variables securely via the environment or modify the thresholds inside the file directly:

*   **`RI_LLM_MODEL`**: Override local Ollama model (Default: `qwen3:4b`)
*   **`RI_MAX_FILES`**: Set repo scan threshold limit (Default: 2000 files)
*   **`RI_CHUNK_SIZE`**: Sets embedding search chunk limitations (Default: 1500 chars)

Example:
```bash
RI_LLM_MODEL="llama3.1" RI_MAX_FILES="500" uv run python main.py ../my_app
```

---

## 🛡️ License

MIT License. See `LICENSE` for more information.

# OpsPilot.ai 🚀

**OpsPilot.ai** is an advanced, agentic AI assistant designed to streamline Incident Response and SRE workflows. Leveraging the power of CrewAI, RAG (Retrieval-Augmented Generation), and modern LLMs (Google Gemini), OpsPilot automates log analysis, root cause identification, and remediation planning.

## 🌟 Features

- **Automated Incident Analysis**: Intelligently parses and analyzes logs to detect anomalies.
- **Root Cause Analysis (RCA)**: Uses multi-agent collaboration to pinpoint the exact source of failures.
- **Smart Remediation**: Suggests actionable fixes based on historical data and best practices.
- **Comprehensive Reporting**: Generates detailed incident reports for post-mortem analysis.
- **RAG Integration**: semantic search through historical incident data using vector embeddings (stored as JSON; cosine similarity computed in-app).
- **Observability**: Built-in Prometheus instrumentation for real-time monitoring.

## 🏗️ Architecture

The system follows a microservices-based architecture powered by Docker containers.

```mermaid
graph TD
    Client[Client / User] -->|HTTP Request| API[FastAPI Application]
    
    subgraph "Core Services"
        API -->|Logging| Logs[Structured Logging]
        API -->|Metrics| Prom[Prometheus]
        API -->|Caching| Redis[Redis]
    end
    
    subgraph "Agentic Workflow (CrewAI)"
        API -->|Trigger| Crew[OpsCrew\n(Manager)]
        Crew --> Agent1[Log Analyst Agent]
        Crew --> Agent2[RCA Agent]
        Crew --> Agent3[Fix Suggester Agent]
        Crew --> Agent4[Report Generator Agent]
    end
    
    subgraph "Data Layer"
        Crew -->|Vector Search| DB[(PostgreSQL)]
        API -->|CRUD| DB
    end

    classDef service fill:#f9f,stroke:#333,stroke-width:2px;
    classDef agent fill:#bbf,stroke:#333,stroke-width:2px;
    classDef db fill:#bfb,stroke:#333,stroke-width:2px;
    
    class API,Redis,Prom service;
    class Agent1,Agent2,Agent3,Agent4,Crew agent;
    class DB db;
```

## 🛠️ Tech Stack

- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **AI/Agents**: [CrewAI](https://crewai.com/), [LangChain](https://langchain.com/)
- **LLM**: Google Gemini
- **Database**: PostgreSQL (embeddings stored as JSON, nearest-neighbour search done in-app)
- **Caching**: Redis
- **Monitoring**: Prometheus
- **Containerization**: Docker & Docker Compose

## 🚀 Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.10+ (for local development)
- Google AI Studio API Key

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/OpsPilot.ai.git
   cd OpsPilot.ai
   ```

2. **Configure Environment**:
   Create a `.env` file in the root directory:
   ```env
   GOOGLE_API_KEY=your_google_api_key_here
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=postgres
   POSTGRES_DB=opspilot
   DATABASE_URL=postgresql://postgres:postgres@db:5432/opspilot
   ```

### LLM provider: OpenRouter (default) / Gemini (optional)

By default the app uses **OpenRouter** with the **DeepSeek** model. Set the provider in your
`.env` — the app defaults to `openrouter` when no key variables are set:

```env
LLM_PROVIDER=openrouter                     # "openrouter" (default) or "google"
OPENROUTER_API_KEY=sk-or-v1-your_key_here
OPENROUTER_MODEL_NAME=deepseek/deepseek-v4-flash-latest
```

To fall back to **Google Gemini** instead, just set the provider and Gemini key:

```env
LLM_PROVIDER=google
GOOGLE_API_KEY=your_google_api_key_here
```

The provider is selected in `app/crew/agents.py` (`get_llm`) and `app/evaluation/judge.py`
(`OpsJudge`). With `LLM_PROVIDER=openrouter`, the crew agents use `LLM("openrouter/...")` and the
evaluation judge uses `ChatOpenAI` pointed at `https://openrouter.ai/api/v1`.

> **Note**: Embeddings (`app/rag/embeddings.py`) still use the Google embedding model when a
> `GOOGLE_API_KEY` is present; otherwise they fall back to a deterministic local hash-based vector
> so the RAG pipeline still works without any paid key.

3. **Run with Docker**:
   ```bash
   docker-compose up --build -d
   ```

4. **Access the API**:
   - Swagger UI: `http://localhost:8000/docs`
   - Health Check: `http://localhost:8000/health`

## 🧪 Testing

Run typical tests using pytest:

```bash
docker-compose run app pytest
```

## ⚖️ Design Trade-offs

These are deliberate decisions worth understanding before extending the project:

**RAG: JSON embeddings + in-app cosine similarity instead of pgvector.**
The `embedding` column stores vectors as `JSON` and `VectorDBService` fetches all incident
rows and computes cosine similarity in Python (`_cosine_similarity`, threshold `0.7`).
- *Why:* no dimension-mismatch headaches, no schema migrations when the embedding model
  changes, and it keeps the DB backend simple.
- *Cost:* **O(n) full scan** per query — no ANN index (no HNSW/IVFFlat), so it does not scale
  to millions of rows. The repo ships `scripts/run_migration.sh` that migrated *from* pgvector
  *to* JSON; going back to pgvector (or FAISS) with an HNSW index is the recommended path
  once the incident corpus grows.

**Redis is a cache, not a task queue.**
`app/core/cache.py` caches the expensive CrewAI result keyed by the MD5 of the logs (24h TTL).
- *Why:* simple, effective dedup of repeated log analysis.
- *Cost:* `POST /analyze` still runs the crew **synchronously/blocking** in the request thread.
  There is no Celery/RQ worker yet — the `run_analysis_task` stub marks where a background
  worker would slot in.

**Synchronous crew execution.**
The whole 4-agent pipeline runs inline per request. Fine for an MVP/demo; for production you
would move it to a worker queue and return a job ID.

## 📊 Benchmarks

> These are **real, measured numbers** from the current codebase
> Caveats are stated next to each number.

### Quality evaluation (LLM-as-a-judge)
Run with `scripts/run_eval.py` against a 3-case golden dataset (DB auth failure, disk-full,
upstream timeout). Scores are the `OpsJudge`'s ratings on a **1–5** scale.

| Metric | Score (avg /5) |
|--------|----------------|
| Accuracy | **5.00** |
| Completeness | **5.00** |
| Actionability | **5.00** |

Latest run details: `Provider: openrouter | Model: ~deepseek/deepseek-v4-flash-latest`, dataset size 3.
A previous run scored **4.67 / 5.00 / 5.00** — the 4.67→5.00 delta is expected **run-to-run
variance** with an LLM judge, which is why these are treated as a regression signal only.


- **Honest caveats:** the dataset is tiny (3 cases) and the cases are unambiguous by design;
  the evaluator is an LLM judge, so scores carry LLM bias and can be optimistic. Treat these
  as a regression signal, not a production benchmark.

### Code coverage
`pytest tests/ --cov=app` reports **72% line coverage** (394 statements, 111 missed) with
**15 tests** passing. Hot spots with thin coverage: the API endpoint, Redis cache (`31%`),
and logging (`54%`) — these are the next places to add tests.

## 🗺️ Future / Roadmap

Planned improvements (not yet implemented):

- **Langfuse observability** — config keys (`LANGFUSE_*`) are already defined in `config.py`
  and `.env`, but Langfuse is **not wired in yet**. Plan: add `langfuse` tracing callbacks to
  the CrewAI `Crew` and the judge so each agent turn + evaluation is traced. (CrewAI already
  advertises its own tracing hook — see the "Tracing is disabled" banner in eval output.)
- **Background worker** (Celery/RQ + Redis queue) so `POST /analyze` returns immediately and
  the crew runs asynchronously (replaces the current blocking call).
- **Structured (JSON) crew output** so `root_cause`, `suggested_fix`, `severity`, and
  `confidence_score` are filled by the model instead of heuristics/docstring parsing.
- **pgvector + HNSW index** for scalable vector search once the corpus grows.
- **Expand the golden dataset** and add the locust load test to CI for meaningful metrics.


Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request


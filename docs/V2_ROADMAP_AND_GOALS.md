# OpsPilot AI v2: Incident Triage & Investigation Copilot
## Strategic Roadmap, Architecture Blueprint, and Grounding Datasets

---

## 1. Executive Summary & Profile Goal

### The Target Profile
**Applied AI Engineer (~1–2 Years of Experience)**
* Demonstrates practical engineering judgment over framework hype.
* Understands cost, latency, security, and context window economics.
* Can design deterministic guardrails and hybrid agent architectures.
* Can build reproducible testbeds and quantitative evaluation pipelines.

### The Strategic Shift: v1 Prototype ➔ v2 Production-Ready Copilot

```
v1 Prototype (Toy Demo Pattern)          v2 Production-Ready (Applied AI Best Practice)
───────────────────────────────────      ────────────────────────────────────────────────
• Burns LLM tokens on raw log stream      • Event-driven: Triggered strictly by alerts
• Chained fake agents without tools      • Hybrid: Fast-path (single LLM) + Multi-Agent Swarm
• LLM used to validate JSON schema        • Deterministic Pydantic validation & secret scrubber
• Embeddings stored as raw JSON in DB     • Native pgvector with HNSW index & metadata filtering
• In-memory full-table scan in Python    • Database-level ANN vector search (sub-millisecond)
• Disconnected mock benchmark scripts    • Self-contained reproducible Chaos Scenario Testbed
• Free-form text / ungrounded claims     • Strict Pydantic contracts with verifiable citations
```

---

## 2. Real-World Datasets for Logs, Deployments & Grounding Docs

To make this project technically credible, you do not need to invent fake errors. The SRE and AIOps research community provides standard, open-source datasets and runbooks.

### A. Production Log Datasets (Free & Public)

1. **Loghub (by LogPAI) — The Industry Standard Academic Benchmark**
   * **Source:** [github.com/logpai/loghub](https://github.com/logpai/loghub)
   * **What it has:** Over 440 million real log lines collected from 16 production systems, including distributed systems (Hadoop, HDFS, Spark, ZooKeeper), web stacks (Apache, Nginx), and OS/cloud infrastructure (OpenStack, Linux, BGL Supercomputer).
   * **Value for this project:** Many datasets in Loghub have ground-truth anomaly labels and line numbers, making them ideal for testing retrieval and hallucination rates.

2. **TrainTicket Chaos & Microservices Benchmark**
   * **Source:** [github.com/FudanSELab/train-ticket](https://github.com/FudanSELab/train-ticket)
   * **What it has:** An open-source benchmark containing 40+ microservices simulating a commercial train-booking platform. Includes fault-injection traces and error logs (e.g., downstream timeouts, database deadlocks, CPU saturation).
   * **Value for this project:** Provides realistic cascading microservice error logs where service A fails because downstream service C timed out.

3. **GAIA (General AI Assistants for IT Operations)**
   * **Source:** AIOps challenge benchmarks (Tsinghua University / NetMan).
   * **What it has:** Labeled fault-injection events with coordinated logs, metrics, and ground-truth root-cause labels.

---

### B. Grounding Documentation & Runbooks (Free & Public)

1. **GitLab Public SRE Runbooks (Gold Standard)**
   * **Source:** [gitlab.com/gitlab-com/runbooks](https://gitlab.com/gitlab-com/runbooks)
   * **What it has:** Real, production-grade markdown runbooks used by GitLab's 24/7 SRE team. Covers alerts like `PostgresConnectionPoolExhaustion`, `RedisMemoryHigh`, `GitalyTimeout`, `SidekiqQueueBacklog`.
   * **Value for this project:** Download 5–10 real runbook markdown files and index them into `pgvector`. When an alert fires for database pool exhaustion, the RAG layer retrieves GitLab's actual remediation steps!

2. **Dan Luu's Post-Mortem Repository**
   * **Source:** [github.com/danluu/post-mortems](https://github.com/danluu/post-mortems)
   * **What it has:** A curated list of real-world public incident post-mortems from Google, AWS, Cloudflare, GitHub, Slack, Stripe, and Discord.
   * **Value for this project:** Perfect seed dataset for historical post-mortem retrieval (e.g., past RCA reports stored in `pgvector`).

---

## 3. v2 Target Architecture

```
                       [Prometheus / Alertmanager / Test Trigger]
                                           │
                                           ▼ POST /api/v2/alerts/triage
                             ┌───────────────────────────┐
                             │    Alert Ingestion &      │
                             │    Secret Sanitization    │
                             └─────────────┬─────────────┘
                                           │
                                           ▼
                             ┌───────────────────────────┐
                             │  Routing & Classification │
                             │  (Severity / Complexity)  │
                             └─────────────┬─────────────┘
                                          / \
             Alert is localized & simple /   \ Alert is Sev-1 / Cascading
                                        /     \
                                       ▼       ▼
    ┌───────────────────────────────────┐    ┌──────────────────────────────────────┐
    │     FAST PATH (Single LLM)        │    │    MULTI-AGENT SWARM (Deep Dive)     │
    │                                   │    │                                      │
    │  • Deterministic pre-fetch:       │    │  • Incident Commander (Orchestrator) │
    │    - Last 50 error logs           │    │  • Telemetry Agent (Logs/Metrics)    │
    │    - Last Git deployment diff     │    │  • Deployment Agent (GitHub/Git)     │
    │    - Service runbook section      │    │  • Runbook Agent (pgvector search)   │
    │  • Single Gemini structured call  │    │  • Adversarial Verifier (Causality)  │
    └─────────────────┬─────────────────┘    └──────────────────┬───────────────────┘
                      │                                         │
                      └────────────────────┬────────────────────┘
                                           │
                                           ▼
                             ┌───────────────────────────┐
                             │ Grounded Incident Report  │
                             │ (Pydantic Schema with     │
                             │  Verifiable Citations)    │
                             └─────────────┬─────────────┘
                                           │
                                           ▼
                             ┌───────────────────────────┐
                             │ Streamlit Triage Card     │
                             │ [Verify & Save to RAG]    │
                             └───────────────────────────┘
```

---

## 4. Step-by-Step Implementation Roadmap

```
Milestone 1: Foundation Clean-up & Native pgvector
  ├── Fix Redis host configuration (read from settings, not hardcoded)
  ├── Remove dead code, duplicate LogEntry models, and sys.stdout hijacking
  ├── Restore native pgvector vector extension and HNSW indexing in PostgreSQL
  └── Align test suite signatures and ensure pytest passes 100%

Milestone 2: Context Enrichment Tools & Sanitizer
  ├── Build deterministic Secret & PII Sanitizer (regex entropy/tokens)
  ├── Build Time-Windowed Log Collector tool ([T-15m, T+5m])
  ├── Build GitHub Deployment & Diff Inspector tool (GitHub API / MCP)
  └── Build Service Runbook Vector Ingestion & Query tool (pgvector)

Milestone 3: Hybrid Triage Engine
  ├── Define Pydantic IncidentTriageResponse contract with strict citations
  ├── Implement Fast-Path Single-Turn LLM pipeline (Gemini 2.5 Flash)
  ├── Implement Multi-Agent Swarm with the Adversarial Verifier (Challenger)
  └── Build the dynamic router (Fast-Path vs. Multi-Agent escalation)

Milestone 4: Chaos Testbed (The Interview Demo Superpower)
  ├── Create mock services (Order Service & Payment Service)
  ├── Build runnable failure scenarios (e.g., "Bad Config Deployment", "DB Pool Starvation")
  └── Connect testbed webhook output to the Engine pipeline

Milestone 5: Frontend UI & Bidirectional Verification Loop
  ├── Update Streamlit UI with an Alert Triage Inbox
  ├── Render citations, log references, and commit diffs cleanly
  └── Implement "Verify & Save to Post-Mortems" button (writes back to pgvector)
```

---

## 5. Differentiation vs. ChatGPT / Claude Desktop with MCP

When interviewers ask: *"Why build an application for this instead of just using ChatGPT with MCP tools?"*, defend with these 5 architectural pillars:

1. **Zero-Touch & Event-Driven (The 3 AM Outage):** ChatGPT requires an engineer awake at 3 AM to open a browser and type prompts. OpsPilot is headless; it triggers on webhooks and posts triage findings to Slack/PagerDuty before the engineer opens their laptop.
2. **Deterministic Context Scoping:** ChatGPT relies on a human to specify time windows, repos, and pod names. OpsPilot programmatically maps `alert.service_name` to the exact repo, calculates `[T - 15m, T + 5m]`, and fetches only bounded evidence.
3. **Security & Secret Redaction:** Connecting commercial chat tools directly to production infrastructure risks sending raw tokens, database passwords, and PII to an external vendor. OpsPilot scrubs all data through a deterministic sanitization layer *before* dispatching to the LLM.
4. **Institutional Memory (Bidirectional RAG):** ChatGPT chats are ephemeral. OpsPilot allows engineers to verify post-mortems with one click, embedding them into `pgvector` to resolve future incidents faster.
5. **Typed Pydantic Contracts:** ChatGPT outputs unpredictable prose. OpsPilot outputs validated JSON objects that can trigger downstream automation, update Jira/PagerDuty tickets, and render rich interactive dashboard cards.

---

## 6. Framework Decision: removing CrewAI, LangGraph for the swarm

### Why CrewAI is being removed

* **Heavy, mostly unused dependency tree.** CrewAI 1.15 pulls `chromadb`, `lancedb`,
  `pdfplumber`, `openpyxl`, `mcp`, `opentelemetry-sdk`, `instructor`, `cel-python`,
  `tokenizers`, `aiosqlite`… — none of which OpsPilot uses. Image size, cold start and CVE
  surface for zero benefit.
* **It owns stdout.** Its `verbose=True` spinners/banners print into the process stream,
  which is the "sys.stdout hijacking" item in Milestone 1.
* **Untyped output.** CrewAI returns free-form markdown, which is exactly why `incident.py`
  needed string heuristics (`infer_confidence`) to fill `confidence_score`.
* **Four round-trips by default.** The sequential crew spends four LLM calls on one incident
  because splitting the work across "roles" is a prompt preference, not a requirement.

### What replaces it

| Stage | Choice | Reason |
|---|---|---|
| **Fast path** (M3) | **No framework** — `app/triage/fast_path.py` | One alert, one structured call, one Pydantic contract, one repair/degrade path. Fully testable with a fake client and no network. |
| **Multi-agent swarm** (M3) | **LangGraph** | Typed state, explicit nodes/edges, conditional escalation, `interrupt()` for the "Verify & Save to Post-Mortems" human loop (M5), checkpointing for long investigations, per-node Langfuse traces. |

LangGraph is chosen over alternatives because it already sits on `langchain-core`
(a present dependency), needs only `langgraph` + a checkpoint store, and maps directly onto
the two things CrewAI never gave us: **typed state** and **resumable execution**.

### Migration status

* `app/llm/**` — provider layer (`gemini` / `openrouter` / `ollama`) with one `complete()` method. **Done.**
* `app/triage/**` — fast-path engine + deterministic evidence bundle + routing pipeline. **Done.**
* `app/crew/**` — kept temporarily because `POST /api/v1/incident/analyze` still imports it.
  Deleting `app/crew/**`, the `crewai` pin in `requirements.txt`, and the v1 `/analyze`
  CrewAI call is the next step after the LangGraph swarm lands (M3).

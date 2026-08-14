# Changelog

All notable changes to **OpsPilot AI** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> Maintenance rule: every change set must add an entry under `[Unreleased]` **in the same
> commit / PR that introduces it**. The full policy is enforced by the repository rules file
> [`.clinerules`](.clinerules) — Rule 1, "Changelog maintenance (mandatory)".

## [Unreleased]

### Added
- **v2 Alert Ingestion API — `POST /api/v2/alerts/triage`** (`app/api/api_v2/endpoints/alerts.py`).
  Accepts Prometheus Alertmanager webhook payloads *and* direct/test triggers, then returns a
  grounded triage response with verifiable citations.
- **Deterministic Secret & PII Sanitizer** (`app/sanitizer/scrubber.py`). Redacts connection-string
  passwords, JWTs, bearer tokens, OpenAI/OpenRouter keys (`sk-...`), Slack (`xoxb-...`),
  GitHub (`ghp_...`), AWS keys, private keys, IPv4 addresses and emails, plus a Shannon-entropy
  pass for unknown high-entropy tokens.
- **Alert Routing & Classification** (`app/sanitizer/ingestion.py`). Sevs-1, cascading, or
  cluster-wide alerts escalate to `multi_agent_swarm`; localized/warning alerts route to
  `fast_path` with bounded `[T-15m, T+5m]` context windows.
- **v2 Pydantic contracts** (`app/schemas/v2/alert.py`): `AlertmanagerWebhookPayload`,
  `DirectAlertIngestRequest`, `SanitizedAlertContext`, `RoutingDecision`, `VerifiableCitation`,
  `IncidentTriageResponse`.
- **Sanitizer utility endpoint** `POST /api/v2/alerts/sanitize` for ad-hoc payload redaction checks.
- **`API_V2_STR` setting** (`app/core/config.py`) so the v2 router prefix is configurable.
- **Test coverage for v2 ingestion** (`tests/test_v2_alerts.py`): fast-path triage, Sev-1 swarm
  escalation, Alertmanager webhook fan-out, and standalone sanitization.
- **Changelog policy and history** — `CHANGELOG.md` (Keep a Changelog / Semantic Versioning) plus
  `.clinerules` Rule 1, which requires every change set to record an entry under `[Unreleased]`
  in the same commit that introduces it.
- **Provider-agnostic LLM client** (`app/llm/client.py`): `gemini`, `openrouter`, and `ollama`
  behind one `ChatClient` contract with a single `complete()` method. Ollama speaks the native
  `/api/chat` endpoint over `httpx` (already pinned), so no new dependency. SDK imports are lazy
  and all failures raise `LLMError` with non-sensitive context only.
- **Fast-path triage engine** (`app/triage/fast_path.py`): one evidence-grounded completion that
  returns `root_cause_summary`, `confidence_score`, `remediation_steps`, and `unknowns`. The
  model may only cite *indexes* into the pre-built evidence bundle
  (`app/triage/evidence.py`); out-of-range indexes are dropped, so invented citations cannot
  reach the report.
- **Deterministic degradation** (`triage_alert` in `app/triage/pipeline.py`): an unreachable
  provider or an unparseable answer yields `status="triaged_degraded"` with confidence `0.25`
  and honest remediation steps instead of a 5xx to the alerting pipeline.
- **Balanced-brace JSON extraction** (`app/llm/json_utils.py`) for fenced, prose-wrapped, and
  nested model output (a `.*?` regex truncates nested objects).
- **Triage settings** in `app/core/config.py`: `OLLAMA_BASE_URL`, `OLLAMA_MODEL_NAME`,
  `TRIAGE_LLM_ENABLED`, `LLM_REQUEST_TIMEOUT_SECONDS`.
- **18 new tests**: `tests/test_llm_providers.py` (provider resolution, Ollama request shape,
  unreachable-provider failure, JSON extraction) and `tests/test_fast_path.py` (grounded draft,
  citation mapping, hallucinated-index dropping, degradation, pipeline assembly).

### Changed
- `app/main.py` now mounts both the v1 router (`/api/v1`) and the v2 router (`/api/v2`).
- `POST /api/v2/alerts/triage` now dispatches `fast_path` alerts to the single-call engine. The
  multi-agent tier returns `status="awaiting_swarm"` with `confidence_score=0.0` instead of a
  placeholder `triaged` report that claimed 0.90+ confidence (honest reporting until M3).
- `IncidentTriageResponse` gains optional `unknowns`, `llm_provider`, and `llm_model` fields —
  backwards compatible (all default to empty/`None`).
- `docker-compose.yml` passes `OLLAMA_BASE_URL`, `OLLAMA_MODEL_NAME`, `TRIAGE_LLM_ENABLED`, and
  `LLM_REQUEST_TIMEOUT_SECONDS` through to the app container.
- `POST /api/v2/alerts/triage` currently returns the sanitized alert context, the routing decision,
  and a grounded stub report. The Fast-Path LLM call and Multi-Agent Swarm execution are the next
  milestones.

### Fixed
- The generic key/value secret rule no longer re-redacts values that a more specific rule already
  labelled, so the most precise placeholder wins (e.g. `api_key=sk-…` →
  `api_key=[REDACTED_API_KEY]`).

### Security
- Alert payloads, labels, and annotations are sanitized *before* any downstream LLM dispatch.

## [0.1.1] - 2026-08-08

### Added
- LLM provider abstraction: OpenRouter (default) in addition to Google Gemini
  (`app/crew/agents.py`, `app/evaluation/judge.py`).
- Deterministic local hash-based fallback embedding so the RAG pipeline works without a paid key
  (`app/rag/embeddings.py`).
- Severity inference and confidence heuristics in the incident endpoint
  (`app/api/api_v1/endpoints/incident.py`).
- Tests for the incident endpoint and the evaluation judge (`tests/test_incident_endpoint.py`,
  `tests/test_judge.py`).
- `INTERVIEW_FLOWS.md` (interview walkthrough) and `docs/V2_ROADMAP_AND_GOALS.md` (v2 roadmap).

### Changed
- Redis host, port, and DB index are now read from settings instead of being hardcoded
  (`app/core/config.py`, `app/core/cache.py`).
- Docker Compose and dependency set updated for multi-provider LLM support; `.dockerignore` added.

### Fixed
- Evaluation judge no longer fails on reasoning-model output; JSON extraction is tolerant of
  preamble text.

## [0.1.0] - 2026-02-12

### Added
- Initial OpsPilot AI release: FastAPI service, CrewAI multi-agent incident analysis
  (Log Analyst → RCA → Fix Suggester → Report Generator).
- PostgreSQL persistence, Redis response cache, Prometheus instrumentation, structured JSON logging.
- In-app RAG over historical incidents (embeddings stored as JSON, cosine similarity in Python).
- LLM-as-a-judge evaluation harness (`scripts/run_eval.py`) with a golden dataset.
- Streamlit frontend and Docker Compose deployment.

[Unreleased]: https://github.com/abhishek09827/Operational-Intelligence-Engine/compare/main...HEAD
[0.1.1]: https://github.com/abhishek09827/Operational-Intelligence-Engine/releases/tag/v0.1.1
[0.1.0]: https://github.com/abhishek09827/Operational-Intelligence-Engine/releases/tag/v0.1.0

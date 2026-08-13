from app.core.config import settings
from app.sanitizer.ingestion import AlertIngestionService
from app.schemas.v2.alert import DirectAlertIngestRequest
from app.tools.github_inspector import DeploymentInspector
from app.tools.log_collector import LogCollector, SequenceLogSource
from app.tools.runbook_store import RunbookStore, chunk_markdown


def make_alert(**overrides):
    payload = {
        "alertname": "HighLatencyWarning",
        "service_name": "checkout-service",
        "severity": "warning",
        "summary": "p99 850ms",
    }
    payload.update(overrides)
    return AlertIngestionService.process_direct_request(DirectAlertIngestRequest(**payload))


# --- Log collector -----------------------------------------------------------


def test_log_collector_filters_by_window_and_service():
    alert = make_alert()
    start = alert.time_window_start.isoformat().replace("+00:00", "Z")
    end = alert.time_window_end.isoformat().replace("+00:00", "Z")
    entries = [
        ("checkout.log", f"{start} INFO checkout-service fine line"),
        ("checkout.log", f"{end} WARN checkout-service slow query duration=850ms"),
        ("checkout.log", "2000-01-01T00:00:00Z WARN checkout-service ancient line"),
        ("checkout.log", f"{start} INFO other-service unrelated"),
    ]
    result = LogCollector(SequenceLogSource(entries)).collect(alert)

    assert result.ok
    joined = "\n".join(fact.snippet for fact in result.facts)
    assert "slow query" in joined
    assert "ancient line" not in joined
    assert "unrelated" not in joined


def test_log_collector_sanitizes_secrets_in_lines():
    alert = make_alert()
    stamp = alert.time_window_start.isoformat().replace("+00:00", "Z")
    entries = [
        (
            "checkout.log",
            f"{stamp} ERROR checkout-service auth failed password=supersecret123 "
            "api_key=sk-1234567890abcdef1234567890",
        )
    ]
    result = LogCollector(SequenceLogSource(entries)).collect(alert)

    assert result.ok
    snippet = result.facts[0].snippet
    assert "supersecret123" not in snippet
    assert "sk-1234567890abcdef1234567890" not in snippet
    assert "[REDACTED_SECRET]" in snippet



def test_log_collector_reports_failure_when_nothing_matches():
    result = LogCollector(SequenceLogSource([])).collect(make_alert())
    assert result.ok is False
    assert "no lines" in result.error


# --- Runbook chunking --------------------------------------------------------

def test_chunk_markdown_splits_on_headings_and_respects_budget():
    body = "# Runbook A\n" + ("step " * 40) + "\n\n## Section B\n" + ("detail " * 40)
    chunks = chunk_markdown(body, budget=120)

    assert chunks
    assert all(len(chunk) <= 120 for chunk in chunks)
    assert any("Runbook A" in chunk for chunk in chunks)


def test_chunk_markdown_handles_empty_input():
    assert chunk_markdown("   ") == []


# --- GitHub inspector --------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeHttp:
    def __init__(self, commits, detail=None):
        self.commits = commits
        self.detail = detail or {}
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(url)
        if url.rstrip("/").endswith("/commits"):
            return _FakeResponse(self.commits)
        return _FakeResponse(self.detail)


def test_github_inspector_requires_repo(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_REPO", "")
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "token")
    result = DeploymentInspector().inspect(make_alert())
    assert result.ok is False
    assert "repository" in result.error


def test_github_inspector_requires_token(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_REPO", "acme/checkout-service")
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "")
    result = DeploymentInspector().inspect(make_alert())
    assert result.ok is False
    assert "GITHUB_TOKEN" in result.error


def test_github_inspector_returns_commits_and_patches(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_REPO", "acme/checkout-service")
    monkeypatch.setattr(settings, "GITHUB_TOKEN", "token")
    http = _FakeHttp(
        commits=[
            {
                "sha": "abcdef1234567890",
                "commit": {"message": "fix: pool sizing", "author": {"date": "2026-09-27T11:40:00Z"}},
            },
            {
                "sha": "1234567890abcdef",
                "commit": {"message": "chore: bump", "author": {"date": "2026-09-27T11:41:00Z"}},
            },
        ],
        detail={"files": [{"filename": "db/pool.py", "status": "modified", "patch": "@@ -1 +1 @@\n-10\n+50"}]},
    )
    result = DeploymentInspector(http_client=http).inspect(make_alert())

    assert result.ok
    assert len(result.facts) == 2
    assert result.facts[0].source_type == "git_diff"
    assert result.facts[0].source_id.startswith("commit:abcdef1234")
    assert "fix: pool sizing" in result.facts[0].snippet
    assert len([url for url in http.calls if "/commits/" in url]) == 2


# --- Runbook store -----------------------------------------------------------


class _FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class _FakeSession:
    def __init__(self, rows=None, error=None):
        self.rows = rows or []
        self.error = error
        self.executed = []
        self.committed = False

    def execute(self, statement, params=None):
        if self.error:
            raise self.error
        self.executed.append((str(statement), params))
        return _FakeResult(self.rows)

    def commit(self):
        self.committed = True


class _FakeEmbedder:
    def generate_embedding(self, text):
        return [0.1] * 768


def test_runbook_search_returns_evidence():
    session = _FakeSession(
        rows=[("Restart the pool", "checkout-runbook.md", "Bump max_connections.")]
    )
    store = RunbookStore(db_session=session, embedding_service=_FakeEmbedder())
    result = store.search(make_alert())

    assert result.ok
    assert len(result.facts) == 1
    assert result.facts[0].source_type == "runbook"
    assert result.facts[0].source_id == "runbook:checkout-runbook.md"
    sql, params = session.executed[0]
    assert "ORDER BY embedding <=>" in sql
    assert params["service"] == "checkout-service"


def test_runbook_search_degrades_without_session():
    result = RunbookStore(db_session=None).search(make_alert())
    assert result.ok is False
    assert "session" in result.error


def test_runbook_search_degrades_on_database_error():
    session = _FakeSession(error=RuntimeError("connection refused"))
    result = RunbookStore(db_session=session, embedding_service=_FakeEmbedder()).search(
        make_alert()
    )
    assert result.ok is False
    assert "runbook search failed" in result.error


def test_runbook_ingest_upserts_chunks():
    session = _FakeSession()
    store = RunbookStore(db_session=session, embedding_service=_FakeEmbedder())
    written = store.ingest_text(
        service_name="checkout-service",
        title="checkout-runbook",
        source="checkout-runbook.md",
        body="# Pool exhaustion\nBump max_connections.\n\n## Verify\nWatch p99.",
    )

    assert written == 1
    assert session.committed
    sql, params = session.executed[0]
    assert "ON CONFLICT" in sql
    assert params["service"] == "checkout-service"
    assert params["vector"].startswith("[0.1")
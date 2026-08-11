"""GitHub deployment & diff inspector.

Answers the question *"what changed right before this alert?"* using the GitHub
REST API for the service's repository inside the alert's time window.

Missing token or missing repo is **not** an error to the caller: the tool returns
``ToolResult(ok=False, error=...)`` so the swarm can state in ``unknowns`` that
no deployment evidence was available.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.schemas.v2.alert import SanitizedAlertContext
from app.tools.base import EvidenceFact, ToolResult

logger = logging.getLogger(__name__)

TOOL_NAME = "github_inspector"
SOURCE_TYPE = "git_diff"
MAX_COMMITS = 5
MAX_DIFFS = 2
MAX_PATCH_CHARS = 600


class DeploymentInspector:
    """Fetches in-window commits and their file patches."""

    def __init__(self, http_client: Any = None) -> None:
        # Injected for tests; created lazily so importing costs nothing.
        self._http = http_client

    def _resolve_repo(self, alert: SanitizedAlertContext) -> Optional[str]:
        return alert.labels.get("repo") or alert.annotations.get("repo") or settings.GITHUB_REPO or None

    def inspect(self, alert: SanitizedAlertContext) -> ToolResult:
        try:
            return self._inspect(alert)
        except Exception as exc:  # never raise out of a tool
            logger.warning("github_inspector failed: %s", exc)
            return ToolResult.failure(TOOL_NAME, f"github lookup failed: {type(exc).__name__}: {exc}"[:300])

    def _inspect(self, alert: SanitizedAlertContext) -> ToolResult:
        repo = self._resolve_repo(alert)
        if not repo:
            return ToolResult.failure(
                TOOL_NAME, "no repository configured (set GITHUB_REPO or alert label 'repo')"
            )
        if not settings.GITHUB_TOKEN:
            return ToolResult.failure(TOOL_NAME, "GITHUB_TOKEN not configured")

        params = {
            "since": alert.time_window_start.isoformat(),
            "until": alert.time_window_end.isoformat(),
            "per_page": str(MAX_COMMITS),
        }
        commits = self._get(f"/repos/{repo}/commits", params)
        if not commits:
            return ToolResult.failure(
                TOOL_NAME, f"no commits in '{repo}' within the alert window"
            )

        facts: List[EvidenceFact] = []
        for index, commit in enumerate(commits[:MAX_COMMITS]):
            sha = commit.get("sha", "")
            message = (commit.get("commit", {}).get("message") or "").split("\n", 1)[0]
            date = commit.get("commit", {}).get("author", {}).get("date", "?")
            patch_block = ""
            if index < MAX_DIFFS and sha:
                patch_block = self._patch_summary(repo, sha)
            facts.append(
                EvidenceFact(
                    source_type=SOURCE_TYPE,
                    source_id=f"commit:{sha[:10] or 'unknown'}",
                    snippet=f"[{date}] {message}\n{patch_block}".strip(),
                ).bounded(MAX_PATCH_CHARS * 2)
            )

        return ToolResult(
            tool=TOOL_NAME,
            ok=True,
            summary=f"{len(facts)} commit(s) to '{repo}' in the alert window",
            facts=facts,
        )

    def _patch_summary(self, repo: str, sha: str) -> str:
        try:
            detail = self._get(f"/repos/{repo}/commits/{sha}", None)
        except Exception as exc:  # diff is best-effort; commits already proved useful
            logger.warning("github diff fetch failed for %s: %s", sha[:10], exc)
            return ""
        files = (detail or {}).get("files") or []
        parts: List[str] = []
        for file in files[:MAX_DIFFS]:
            name = file.get("filename", "?")
            status = file.get("status", "?")
            patch = (file.get("patch") or "").strip()[:MAX_PATCH_CHARS]
            parts.append(f"{status}: {name}\n{patch}")
        return "\n".join(parts)

    def _get(self, path: str, params: Optional[Dict[str, str]]) -> Any:
        import httpx

        url = f"{settings.GITHUB_API_URL.rstrip('/')}{path}"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._http is not None:
            response = self._http.get(url, params=params, headers=headers, timeout=15.0)
        else:
            response = httpx.get(url, params=params, headers=headers, timeout=15.0)
        response.raise_for_status()
        return response.json()

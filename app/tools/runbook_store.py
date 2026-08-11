"""Service runbook ingestion and pgvector retrieval.

The Runbook Agent retrieves grounded remediation steps from the ``runbooks``
table created in ``docker/init.sql`` (native pgvector + HNSW index). Chunking is
deterministic (headings, then packed paragraphs) so a re-ingest produces the
same ``chunk_index`` keys and upserts instead of duplicating rows.

Retrieval uses pgvector's cosine operator server-side; failures (DB down, vector
extension missing, no embeddings) come back as ``ToolResult(ok=False, ...)``.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, List, Optional

from sqlalchemy import text

from app.core.config import settings
from app.schemas.v2.alert import SanitizedAlertContext
from app.tools.base import EvidenceFact, ToolResult

logger = logging.getLogger(__name__)

TOOL_NAME = "runbook_store"
SOURCE_TYPE = "runbook"
CHUNK_CHAR_BUDGET = 700
QUERY_TOP_K = 3

_SEARCH_SQL = """
    SELECT title, source, content
    FROM runbooks
    WHERE service_name = :service OR service_name = 'all'
    ORDER BY embedding <=> CAST(:vector AS vector)
    LIMIT :k
"""

_INSERT_SQL = """
    INSERT INTO runbooks (service_name, title, source, chunk_index, content, embedding)
    VALUES (:service, :title, :source, :chunk_index, :content, :vector)
    ON CONFLICT (service_name, source, chunk_index)
    DO UPDATE SET content = EXCLUDED.content, embedding = EXCLUDED.embedding
"""


def chunk_markdown(text_body: str, budget: int = CHUNK_CHAR_BUDGET) -> List[str]:
    """Deterministic chunking: split on markdown headings, pack to ``budget``."""
    parts = re.split(r"(?m)^(?=#{1,3}\s)", text_body)
    raw = [part.strip() for part in parts if part.strip()]
    if not raw:
        return []

    chunks: List[str] = []
    buffer = ""
    for part in raw:
        candidate = f"{buffer}\n\n{part}".strip() if buffer else part
        if len(candidate) <= budget:
            buffer = candidate
            continue
        if buffer:
            chunks.append(buffer)
        while len(part) > budget:  # pathological long section
            chunks.append(part[:budget])
            part = part[budget:]
        buffer = part
    if buffer:
        chunks.append(buffer)
    return chunks


def _to_pgvector(vector: List[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"


class RunbookStore:
    """Thin persistence layer over the ``runbooks`` table."""

    def __init__(self, db_session: Any = None, embedding_service: Any = None) -> None:
        self.db = db_session
        self._embedder = embedding_service

    @property
    def embedder(self) -> Any:
        if self._embedder is None:
            from app.rag.embeddings import EmbeddingService

            self._embedder = EmbeddingService()
        return self._embedder

    # --- ingestion -----------------------------------------------------------

    def ingest_text(self, service_name: str, title: str, source: str, body: str) -> int:
        """Chunk, embed, and upsert one runbook. Returns rows written."""
        chunks = chunk_markdown(body)
        if not self.db:
            raise RuntimeError("no database session configured")
        for index, chunk in enumerate(chunks):
            vector = _to_pgvector(self.embedder.generate_embedding(chunk))
            self.db.execute(
                text(_INSERT_SQL),
                {
                    "service": service_name,
                    "title": title,
                    "source": source,
                    "chunk_index": index,
                    "content": chunk,
                    "vector": vector,
                },
            )
        self.db.commit()
        return len(chunks)

    def ingest_directory(self, runbook_dir: Optional[str] = None) -> int:
        """Ingest every ``*.md`` under ``RUNBOOK_DIR``; filename stem = service tag."""
        root = Path(runbook_dir or settings.RUNBOOK_DIR)
        if not root.exists():
            return 0
        written = 0
        for path in sorted(root.glob("*.md")):
            body = path.read_text(encoding="utf-8", errors="replace")
            written += self.ingest_text(path.stem, path.stem, path.name, body)
        return written

    # --- retrieval -----------------------------------------------------------

    def search(self, alert: SanitizedAlertContext) -> ToolResult:
        try:
            return self._search(alert)
        except Exception as exc:
            logger.warning("runbook_store search failed: %s", exc)
            return ToolResult.failure(TOOL_NAME, f"runbook search failed: {type(exc).__name__}"[:300])

    def _search(self, alert: SanitizedAlertContext) -> ToolResult:
        if self.db is None:
            return ToolResult.failure(TOOL_NAME, "no database session configured")

        query = f"{alert.alertname} {alert.service_name} {alert.summary}".strip()
        vector = _to_pgvector(self.embedder.generate_embedding(query))
        result = self.db.execute(
            text(_SEARCH_SQL),
            {"service": alert.service_name, "vector": vector, "k": QUERY_TOP_K},
        )
        rows = list(result.fetchall())

        if not rows:
            return ToolResult.failure(
                TOOL_NAME, f"no runbook chunks indexed for '{alert.service_name}'"
            )

        facts = [
            EvidenceFact(
                source_type=SOURCE_TYPE,
                source_id=f"runbook:{row[1]}",
                snippet=f"# {row[0]}\n{row[2]}",
            ).bounded(800)
            for row in rows
        ]
        return ToolResult(
            tool=TOOL_NAME,
            ok=True,
            summary=f"{len(facts)} runbook chunk(s) for '{alert.service_name}'",
            facts=facts,
        )

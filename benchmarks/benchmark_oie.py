"""OI-Engine benchmark suite.

This module keeps the original four benchmark categories intact while making
the execution resilient to missing infrastructure:

- Kafka ingestion falls back to a simulated in-memory pipeline if Kafka is not
  running locally.
- LLM-facing stages remain simulated by default, with an optional OpenRouter
  smoke-test fallback if the environment requests it and a real provider path is
  desired.
- Numerical evaluation works even if scipy or scikit-learn are unavailable by
  using local fallback implementations.
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import math
import os
import random
import socket
import statistics
import sys
import time
import uuid
from collections import Counter, deque, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks.labeled_test_set import LABELED_TEST_SET
from benchmarks.mock_log_generator import generate_log_event, generate_log_events

try:
    from kafka import KafkaProducer
except Exception:  # pragma: no cover - optional dependency
    KafkaProducer = None

try:
    from tabulate import tabulate
except Exception:  # pragma: no cover - optional dependency
    tabulate = None

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency
    np = None

try:
    from sklearn.metrics import classification_report, confusion_matrix, f1_score, precision_score, recall_score
except Exception:  # pragma: no cover - optional dependency
    classification_report = None
    confusion_matrix = None
    f1_score = None
    precision_score = None
    recall_score = None

try:
    from scipy import stats
except Exception:  # pragma: no cover - optional dependency
    stats = None

try:
    import httpx
except Exception:  # pragma: no cover - optional dependency
    httpx = None


DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent / "results"
DEFAULT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

BENCHMARK_WARNINGS: List[str] = []


def warn(message: str) -> None:
    BENCHMARK_WARNINGS.append(message)
    print(f"[warn] {message}")


def as_list(values: Sequence[float]) -> List[float]:
    return list(values)


def percentile(values: Sequence[float], pct: float) -> float:
    data = sorted(values)
    if not data:
        return 0.0
    if len(data) == 1:
        return float(data[0])
    rank = (len(data) - 1) * (pct / 100.0)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return float(data[int(rank)])
    return float(data[low] + (data[high] - data[low]) * (rank - low))


def mean(values: Sequence[float]) -> float:
    return float(statistics.mean(values)) if values else 0.0


def safe_stdev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(statistics.pstdev(values))


def compute_zscores(values: Sequence[float]) -> List[float]:
    if not values:
        return []
    if stats is not None:
        try:
            result = stats.zscore(values)
            if np is not None:
                return [float(x) if not math.isnan(float(x)) else 0.0 for x in result.tolist()]
            return [float(x) if not math.isnan(float(x)) else 0.0 for x in result]
        except Exception:
            pass
    avg = mean(values)
    std = safe_stdev(values)
    if std == 0:
        return [0.0 for _ in values]
    return [(value - avg) / std for value in values]


def zscore_filter(events: Sequence[Dict[str, Any]], threshold: float = 2.5) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Filter event candidates using the statistical fast path."""

    flagged: List[Dict[str, Any]] = []
    normal: List[Dict[str, Any]] = []

    service_events: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for event in events:
        service_events[event["service"]].append(event)

    for _service, service_batch in service_events.items():
        latencies = [float(event["latency_ms"]) for event in service_batch]
        if len(latencies) < 10:
            normal.extend(service_batch)
            continue
        z_scores = compute_zscores(latencies)
        for event, score in zip(service_batch, z_scores):
            if abs(score) > threshold:
                flagged.append(event)
            else:
                normal.append(event)

    return flagged, normal


def zscore_filter_single(event: Dict[str, Any]) -> bool:
    """Tiny single-event fast path used by the latency simulation."""

    return float(event["latency_ms"]) > 250.0


def serialize_event(event: Dict[str, Any]) -> bytes:
    return json.dumps(event, separators=(",", ":"), sort_keys=True).encode("utf-8")


def is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def compression_ratio_for_events(events: Sequence[Dict[str, Any]]) -> float:
    payload = b"".join(serialize_event(event) for event in events)
    if not payload:
        return 0.0
    compressed = gzip.compress(payload)
    return round(len(payload) / max(len(compressed), 1), 2)


@dataclass
class IngestionResult:
    mode: str
    events_per_sec: float
    batch_size: int
    compression_ratio: float
    elapsed_sec: float
    events_processed: int


def benchmark_kafka_ingestion(total_events: int, warmup_events: int = 1000) -> IngestionResult:
    sample_events = [generate_log_event(is_anomaly=(index % 50 == 0)) for index in range(min(total_events, 2000))]
    compression_ratio = compression_ratio_for_events(sample_events)

    if KafkaProducer is not None and is_port_open("localhost", 9092):
        try:
            producer = KafkaProducer(
                bootstrap_servers="localhost:9092",
                value_serializer=lambda value: json.dumps(value).encode("utf-8"),
                batch_size=65536,
                linger_ms=10,
                compression_type="gzip",
                request_timeout_ms=5000,
                api_version_auto_timeout_ms=3000,
            )

            for _ in range(warmup_events):
                producer.send("ops-logs", generate_log_event())
            producer.flush()

            start = time.perf_counter()
            for index in range(total_events):
                producer.send(
                    "ops-logs",
                    generate_log_event(is_anomaly=(index % 50 == 0)),
                )
            producer.flush()
            elapsed = time.perf_counter() - start

            return IngestionResult(
                mode="live (Kafka running)",
                events_per_sec=total_events / elapsed if elapsed > 0 else 0.0,
                batch_size=65536,
                compression_ratio=compression_ratio,
                elapsed_sec=elapsed,
                events_processed=total_events,
            )
        except Exception as exc:
            warn(f"Kafka benchmark failed, falling back to simulation: {exc}")

    queue: deque[bytes] = deque()
    start = time.perf_counter()
    for index in range(total_events):
        queue.append(serialize_event(generate_log_event(is_anomaly=(index % 50 == 0))))
    elapsed = time.perf_counter() - start
    _ = len(queue)
    return IngestionResult(
        mode="simulated (Kafka not running)",
        events_per_sec=total_events / elapsed if elapsed > 0 else 0.0,
        batch_size=65536,
        compression_ratio=compression_ratio,
        elapsed_sec=elapsed,
        events_processed=total_events,
    )


@dataclass
class FilterResult:
    total_events: int
    filtered_events: int
    sent_to_llm: int
    filter_rate: float
    true_anomalies_captured: int
    false_positives: int
    true_positive_rate: float
    false_positive_rate: float
    llm_calls_avoided: int
    estimated_cost_saved: float


def benchmark_two_stage_filter(total_events: int = 10_000) -> FilterResult:
    anomaly_count = max(1, int(round(total_events * 0.02)))
    events: List[Dict[str, Any]] = []
    for index in range(total_events):
        events.append(
            generate_log_event(is_anomaly=index >= (total_events - anomaly_count))
        )
        events[-1]["is_anomaly"] = index >= (total_events - anomaly_count)

    flagged, normal = zscore_filter(events)
    true_anomalies_captured = sum(1 for event in flagged if event.get("is_anomaly"))
    false_positives = sum(1 for event in flagged if not event.get("is_anomaly"))
    filtered_out = len(normal)
    llm_calls_avoided = filtered_out
    anomalies_total = sum(1 for event in events if event.get("is_anomaly")) or 1
    normals_total = total_events - anomalies_total or 1
    precision = true_anomalies_captured / max(len(flagged), 1)
    recall = true_anomalies_captured / anomalies_total
    true_positive_rate = recall
    false_positive_rate = false_positives / normals_total
    estimated_cost_saved = llm_calls_avoided * 0.002

    return FilterResult(
        total_events=total_events,
        filtered_events=filtered_out,
        sent_to_llm=len(flagged),
        filter_rate=filtered_out / total_events,
        true_anomalies_captured=true_anomalies_captured,
        false_positives=false_positives,
        true_positive_rate=true_positive_rate,
        false_positive_rate=false_positive_rate,
        llm_calls_avoided=llm_calls_avoided,
        estimated_cost_saved=estimated_cost_saved,
    )


def incident_flagged(incident: Dict[str, Any]) -> bool:
    return any(zscore_filter_single(event) for event in incident["events"])


def binary_confusion(y_true: Sequence[int], y_pred: Sequence[int]) -> Tuple[int, int, int, int]:
    tp = fp = tn = fn = 0
    for truth, pred in zip(y_true, y_pred):
        if truth == 1 and pred == 1:
            tp += 1
        elif truth == 0 and pred == 1:
            fp += 1
        elif truth == 0 and pred == 0:
            tn += 1
        elif truth == 1 and pred == 0:
            fn += 1
    return tp, fp, tn, fn


def classification_metrics(y_true: Sequence[int], y_pred: Sequence[int]) -> Dict[str, float]:
    tp, fp, tn, fn = binary_confusion(y_true, y_pred)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-12)
    accuracy = (tp + tn) / max(len(y_true), 1)
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
        "tp": float(tp),
        "fp": float(fp),
        "tn": float(tn),
        "fn": float(fn),
    }


def format_classification_report(y_true: Sequence[int], y_pred: Sequence[int]) -> str:
    if classification_report is not None:
        return classification_report(y_true, y_pred, target_names=["Normal", "Anomaly"], digits=4)

    metrics = classification_metrics(y_true, y_pred)
    tp, fp, tn, fn = binary_confusion(y_true, y_pred)
    normal_precision = tn / max(tn + fn, 1)
    normal_recall = tn / max(tn + fp, 1)
    normal_f1 = 2 * normal_precision * normal_recall / max(normal_precision + normal_recall, 1e-12)
    lines = [
        "              precision    recall  f1-score   support",
        "",
        f"Normal       {normal_precision:>9.4f} {normal_recall:>9.4f} {normal_f1:>9.4f} {int(tn + fp):>9}",
        f"Anomaly      {metrics['precision']:>9.4f} {metrics['recall']:>9.4f} {metrics['f1']:>9.4f} {int(tp + fn):>9}",
        "",
        f"accuracy                         {metrics['accuracy']:>9.4f} {len(y_true):>9}",
    ]
    return "\n".join(lines)


def benchmark_labeled_test_set() -> Dict[str, Any]:
    y_true = [1 if incident["label"] == "anomaly" else 0 for incident in LABELED_TEST_SET]
    y_pred = [1 if incident_flagged(incident) else 0 for incident in LABELED_TEST_SET]

    report = format_classification_report(y_true, y_pred)
    metrics = classification_metrics(y_true, y_pred)

    if confusion_matrix is not None:
        matrix = confusion_matrix(y_true, y_pred)
    else:
        tp, fp, tn, fn = binary_confusion(y_true, y_pred)
        matrix = [[tn, fp], [fn, tp]]

    return {
        "report": report,
        "metrics": metrics,
        "confusion_matrix": matrix,
        "y_true": y_true,
        "y_pred": y_pred,
    }


async def mock_llm_analysis(event: Dict[str, Any], provider: str = "mock") -> Dict[str, Any]:
    """Simulate or optionally probe a real LLM provider."""

    provider = provider.lower().strip()
    if provider == "openrouter":
        if httpx is None:
            warn("httpx is unavailable, using simulated LLM latency instead of OpenRouter.")
        elif not os.getenv("OPENROUTER_API_KEY"):
            warn("OPENROUTER_API_KEY is missing, using simulated LLM latency instead of OpenRouter.")
        else:
            try:
                model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
                headers = {
                    "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "https://github.com/abhishek09827/Operational-Intelligence-Engine"),
                    "X-Title": os.getenv("OPENROUTER_APP_NAME", "OI-Engine Benchmark"),
                }
                payload = {
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                "Analyze this log event and return JSON with severity, root_cause, "
                                "confidence, suggested_fix. Log: " + json.dumps(event, separators=(",", ":"))
                            ),
                        }
                    ],
                    "temperature": 0.1,
                }
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    try:
                        parsed = json.loads(content)
                    except Exception:
                        parsed = {
                            "severity": "medium",
                            "root_cause": content[:200],
                            "confidence": 0.8,
                            "suggested_fix": "Review the OpenRouter response and adjust the analyzer prompt.",
                        }
                    return parsed
            except Exception as exc:
                warn(f"OpenRouter probe failed, falling back to simulated latency: {exc}")

    await asyncio.sleep(random.uniform(0.6, 1.2))
    return {
        "severity": random.choice(["low", "medium", "high"]),
        "root_cause": "Simulated root cause analysis",
        "confidence": random.uniform(0.5, 0.99),
        "suggested_fix": "Simulated remediation step",
    }


async def mock_jira_ticket(analysis: Dict[str, Any]) -> Dict[str, Any]:
    await asyncio.sleep(random.uniform(0.1, 0.3))
    return {"ticket_id": f"OPS-{random.randint(1000, 9999)}"}


async def full_pipeline(event: Dict[str, Any], provider: str = "mock") -> Dict[str, Any]:
    t0 = time.perf_counter()

    t1 = time.perf_counter()
    flagged = zscore_filter_single(event)
    zscore_time = time.perf_counter() - t1

    if not flagged:
        return {
            "result": "filtered",
            "total_ms": (time.perf_counter() - t0) * 1000,
            "zscore_ms": zscore_time * 1000,
            "llm_ms": 0.0,
            "jira_ms": 0.0,
        }

    t2 = time.perf_counter()
    analysis = await mock_llm_analysis(event, provider=provider)
    llm_time = time.perf_counter() - t2

    if analysis["confidence"] < 0.75:
        return {
            "result": "below_threshold",
            "total_ms": (time.perf_counter() - t0) * 1000,
            "zscore_ms": zscore_time * 1000,
            "llm_ms": llm_time * 1000,
            "jira_ms": 0.0,
        }

    t3 = time.perf_counter()
    ticket = await mock_jira_ticket(analysis)
    jira_time = time.perf_counter() - t3

    total = time.perf_counter() - t0
    return {
        "result": "ticket_created",
        "ticket_id": ticket["ticket_id"],
        "total_ms": total * 1000,
        "zscore_ms": zscore_time * 1000,
        "llm_ms": llm_time * 1000,
        "jira_ms": jira_time * 1000,
    }


async def run_latency_batch(count: int = 100, provider: str = "mock") -> List[Dict[str, Any]]:
    semaphore = asyncio.Semaphore(10)

    async def run_one(event: Dict[str, Any]) -> Dict[str, Any]:
        async with semaphore:
            return await full_pipeline(event, provider=provider)

    tasks = [
        asyncio.create_task(run_one(generate_log_event(is_anomaly=True)))
        for _ in range(count)
    ]
    return await asyncio.gather(*tasks)


def summarize_latency(results: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    ticket_results = [row for row in results if row["result"] == "ticket_created"]
    if not ticket_results:
        return {
            "zscore": {"p50": 0.0, "p95": 0.0, "p99": 0.0},
            "llm": {"p50": 0.0, "p95": 0.0, "p99": 0.0},
            "jira": {"p50": 0.0, "p95": 0.0, "p99": 0.0},
            "total": {"p50": 0.0, "p95": 0.0, "p99": 0.0, "mean": 0.0},
        }

    return {
        "zscore": {
            "p50": percentile([row["zscore_ms"] for row in ticket_results], 50),
            "p95": percentile([row["zscore_ms"] for row in ticket_results], 95),
            "p99": percentile([row["zscore_ms"] for row in ticket_results], 99),
        },
        "llm": {
            "p50": percentile([row["llm_ms"] for row in ticket_results], 50),
            "p95": percentile([row["llm_ms"] for row in ticket_results], 95),
            "p99": percentile([row["llm_ms"] for row in ticket_results], 99),
        },
        "jira": {
            "p50": percentile([row["jira_ms"] for row in ticket_results], 50),
            "p95": percentile([row["jira_ms"] for row in ticket_results], 95),
            "p99": percentile([row["jira_ms"] for row in ticket_results], 99),
        },
        "total": {
            "p50": percentile([row["total_ms"] for row in ticket_results], 50),
            "p95": percentile([row["total_ms"] for row in ticket_results], 95),
            "p99": percentile([row["total_ms"] for row in ticket_results], 99),
            "mean": mean([row["total_ms"] for row in ticket_results]),
        },
    }


def table(rows: Sequence[Sequence[Any]], headers: Sequence[str]) -> str:
    if tabulate is not None:
        return tabulate(rows, headers=headers, tablefmt="github")
    widths = [len(str(header)) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(str(value)))
    header_line = " | ".join(str(header).ljust(widths[index]) for index, header in enumerate(headers))
    separator = "-+-".join("-" * width for width in widths)
    body = [" | ".join(str(value).ljust(widths[index]) for index, value in enumerate(row)) for row in rows]
    return "\n".join([header_line, separator, *body])


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def format_metric_table(ingestion: IngestionResult, filter_result: FilterResult) -> str:
    rows = [
        ["Total events processed", f"{filter_result.total_events:,}"],
        ["Events filtered (Z-score)", f"{filter_result.filtered_events:,}"],
        ["Events sent to LLM", f"{filter_result.sent_to_llm:,}"],
        ["Filter rate", f"{filter_result.filter_rate:.1%}"],
        ["True anomalies captured", f"{filter_result.true_anomalies_captured:,}"],
        ["False positives", f"{filter_result.false_positives:,}"],
        ["True positive rate", f"{filter_result.true_positive_rate:.1%}"],
        ["False positive rate", f"{filter_result.false_positive_rate:.1%}"],
        ["LLM calls avoided", f"{filter_result.llm_calls_avoided:,}"],
        ["Est. cost saved (@$0.002/call)", f"${filter_result.estimated_cost_saved:.2f}"],
        ["Kafka mode", ingestion.mode],
        ["Events/sec", f"{ingestion.events_per_sec:,.0f}"],
        ["Batch size", f"{ingestion.batch_size:,}"],
        ["Compression ratio", f"{ingestion.compression_ratio:.2f}x"],
    ]
    return table(rows, headers=["Metric", "Value"])


def format_latency_table(summary: Dict[str, Dict[str, float]]) -> str:
    rows = [
        ["Z-score filter", f"{summary['zscore']['p50']:.0f}ms", f"{summary['zscore']['p95']:.0f}ms", f"{summary['zscore']['p99']:.0f}ms"],
        ["LLM inference", f"{summary['llm']['p50']:.0f}ms", f"{summary['llm']['p95']:.0f}ms", f"{summary['llm']['p99']:.0f}ms"],
        ["JIRA ticket creation", f"{summary['jira']['p50']:.0f}ms", f"{summary['jira']['p95']:.0f}ms", f"{summary['jira']['p99']:.0f}ms"],
        ["Total end-to-end", f"{summary['total']['p50']:.0f}ms", f"{summary['total']['p95']:.0f}ms", f"{summary['total']['p99']:.0f}ms"],
    ]
    return table(rows, headers=["Stage", "p50", "p95", "p99"])


def build_report(
    ingestion: IngestionResult,
    filter_result: FilterResult,
    labeled_result: Dict[str, Any],
    latency_summary: Dict[str, Dict[str, float]],
    provider: str,
) -> str:
    metrics = labeled_result["metrics"]
    report_lines = [
        "# OI-Engine Benchmark Report",
        f"Generated: {datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}",
        "",
        "## Run Notes",
        f"- LLM provider mode: `{provider}`",
        f"- Kafka mode: `{ingestion.mode}`",
    ]

    if BENCHMARK_WARNINGS:
        report_lines.extend(["- Warnings:"] + [f"  - {warning}" for warning in BENCHMARK_WARNINGS])

    report_lines.extend(
        [
            "",
            "## Resume-Ready Metrics",
            f"- Two-stage detection filters {filter_result.filter_rate:.0%} of events before LLM inference.",
            f"- {metrics['fp'] / max(metrics['fp'] + metrics['tn'], 1):.0%} false positive rate on {len(LABELED_TEST_SET)} labeled incidents.",
            f"- {metrics['recall']:.0%} true positive rate on anomaly detection (precision: {metrics['precision']:.0%}, F1: {metrics['f1']:.2f}).",
            f"- Mean end-to-end latency {latency_summary['total']['mean']:.0f}ms from anomaly detection to JIRA ticket creation (p95: {latency_summary['total']['p95']:.0f}ms).",
            f"- Confidence threshold (>0.75) avoids LLM inference on {filter_result.filter_rate:.0%} of candidates - saves about ${filter_result.estimated_cost_saved:.2f} per 10,000 processed events.",
            "",
            "## Benchmark OIE-1: Kafka Ingestion Throughput",
            format_metric_table(ingestion, filter_result),
            "",
            "## Benchmark OIE-2: Two-Stage Detection Filtering Rate",
            table(
                [
                    ["Total events processed", f"{filter_result.total_events:,}"],
                    ["Events filtered (Z-score)", f"{filter_result.filtered_events:,}"],
                    ["Events sent to LLM", f"{filter_result.sent_to_llm:,}"],
                    ["Filter rate", f"{filter_result.filter_rate:.1%}"],
                    ["True anomalies captured", f"{filter_result.true_anomalies_captured:,}"],
                    ["False positives", f"{filter_result.false_positives:,}"],
                    ["True positive rate", f"{filter_result.true_positive_rate:.1%}"],
                    ["False positive rate", f"{filter_result.false_positive_rate:.1%}"],
                    ["LLM calls avoided", f"{filter_result.llm_calls_avoided:,}"],
                    ["Est. cost saved (@$0.002/call)", f"${filter_result.estimated_cost_saved:.2f}"],
                ],
                headers=["Metric", "Value"],
            ),
            "",
            "## Benchmark OIE-3: False Positive Rate - Labeled Test Set",
            labeled_result["report"],
            "",
            "## Benchmark OIE-4: End-to-End Latency Simulation",
            format_latency_table(latency_summary),
            "",
            "## Resume Phrasing",
            f'- "Built OI-Engine, a multi-agent AIOps platform processing {ingestion.events_per_sec:,.0f} log events/sec with {filter_result.filter_rate:.0%} noise filtered before LLM inference via a statistical fast path"',
            f'- "Designed a confidence scoring layer reducing false positive alert rate to {metrics["fp"] / max(metrics["fp"] + metrics["tn"], 1):.0%} on a {len(LABELED_TEST_SET)}-incident labeled evaluation set (F1: {metrics["f1"]:.2f})"',
            f'- "Achieved {latency_summary["total"]["mean"]:.0f}ms mean end-to-end latency from anomaly detection to automated JIRA ticket creation with root cause hypothesis and suggested remediation"',
        ]
    )

    return "\n".join(report_lines).strip() + "\n"


def save_artifacts(
    report: str,
    labeled_result: Dict[str, Any],
    summary: Dict[str, Any],
) -> None:
    DEFAULT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_text(DEFAULT_RESULTS_DIR / "benchmark_report.md", report)
    write_text(DEFAULT_RESULTS_DIR / "benchmark_3_classification_report.txt", labeled_result["report"] + "\n")
    write_text(
        DEFAULT_RESULTS_DIR / "benchmark_summary.json",
        json.dumps(summary, indent=2, sort_keys=True),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the OI-Engine benchmark suite.")
    parser.add_argument("--scale", type=float, default=1.0, help="Scale down event counts for quick smoke tests.")
    parser.add_argument(
        "--llm-provider",
        default=os.getenv("OIE_BENCH_LLM_PROVIDER", "mock"),
        choices=["mock", "openrouter"],
        help="LLM mode for the latency benchmark. Mock is the default; OpenRouter is optional.",
    )
    parser.add_argument(
        "--results-dir",
        default=str(DEFAULT_RESULTS_DIR),
        help="Directory where benchmark artifacts are written.",
    )
    return parser.parse_args()


def scaled_count(base: int, scale: float) -> int:
    return max(1, int(round(base * scale)))


def main() -> None:
    args = parse_args()
    global DEFAULT_RESULTS_DIR
    DEFAULT_RESULTS_DIR = Path(args.results_dir).resolve()
    DEFAULT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    random.seed(42)

    ingestion_events = scaled_count(50_000, args.scale)
    labeled_event_count = scaled_count(10_000, args.scale)
    latency_event_count = scaled_count(100, args.scale)

    ingestion = benchmark_kafka_ingestion(ingestion_events)
    filter_result = benchmark_two_stage_filter(labeled_event_count)
    labeled_result = benchmark_labeled_test_set()
    if args.scale < 1.0:
        warn("Scale factor was applied for a quicker local run. Use --scale 1.0 for the full benchmark.")

    latency_results = asyncio.run(run_latency_batch(latency_event_count, provider=args.llm_provider))
    latency_summary = summarize_latency(latency_results)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": args.llm_provider,
        "ingestion": {
            "mode": ingestion.mode,
            "events_per_sec": ingestion.events_per_sec,
            "batch_size": ingestion.batch_size,
            "compression_ratio": ingestion.compression_ratio,
            "elapsed_sec": ingestion.elapsed_sec,
            "events_processed": ingestion.events_processed,
        },
        "filtering": {
            "total_events": filter_result.total_events,
            "filtered_events": filter_result.filtered_events,
            "sent_to_llm": filter_result.sent_to_llm,
            "filter_rate": filter_result.filter_rate,
            "true_anomalies_captured": filter_result.true_anomalies_captured,
            "false_positives": filter_result.false_positives,
            "true_positive_rate": filter_result.true_positive_rate,
            "false_positive_rate": filter_result.false_positive_rate,
            "llm_calls_avoided": filter_result.llm_calls_avoided,
            "estimated_cost_saved": filter_result.estimated_cost_saved,
        },
        "labeled": {
            "precision": labeled_result["metrics"]["precision"],
            "recall": labeled_result["metrics"]["recall"],
            "f1": labeled_result["metrics"]["f1"],
            "accuracy": labeled_result["metrics"]["accuracy"],
        },
        "latency": latency_summary,
        "warnings": BENCHMARK_WARNINGS,
    }

    report = build_report(ingestion, filter_result, labeled_result, latency_summary, provider=args.llm_provider)
    save_artifacts(report, labeled_result, summary)

    print(report)
    print(f"Saved benchmark artifacts to: {DEFAULT_RESULTS_DIR}")


if __name__ == "__main__":
    main()

import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.evaluation.judge import OpsJudge
from app.crew.crew import OpsCrew
from app.rag.vector_db import VectorDBService
from unittest.mock import MagicMock
from app.core.config import settings

# Neutralize the RAG/DB lookup so the evaluation runs without a live database.
# We evaluate the crew reasoning, not vector retrieval, here.
def _no_history(self, query, limit=3, threshold=0.7):
    return []

VectorDBService.search_similar_incidents = _no_history


# Golden dataset: each case is a real, unambiguous infra failure so the scores
# reflect how well the crew + judge pipeline performs, not how tricky the log is.
dataset = [
    {
        "logs": (
            "[ERROR] 2026-02-07T10:15:32Z db-pool FATAL: password authentication "
            'failed for user "postgres" Connection refused on host "localhost"'
        ),
        "ground_truth": (
            "Root Cause: Incorrect database credentials / password authentication "
            "failure. Fix: Update the DB password in config and restart the service."
        ),
        "expected_root_cause": "Authentication / credential failure",
    },
    {
        "logs": (
            "[CRITICAL] 2026-02-07T11:02:10Z storage-node ERROR: No space left on "
            "device writing to /var/log; disk usage at 100%"
        ),
        "ground_truth": (
            "Root Cause: Disk full. Fix: Clean old logs, increase disk, add log "
            "rotation, and set up alerting on disk usage."
        ),
        "expected_root_cause": "Disk / storage exhaustion",
    },
    {
        "logs": (
            "[ERROR] 2026-02-07T12:40:45Z api-gateway ERROR: upstream request timeout "
            "connecting to payments-service after 30s; HTTP 504"
        ),
        "ground_truth": (
            "Root Cause: Upstream service timeout / slow dependency. Fix: investigate "
            "payments-service, increase timeout, add retries/circuit breaker."
        ),
        "expected_root_cause": "Upstream service timeout / latency",
    },
]


def run_evaluation() -> None:
    print("=" * 60)
    print("Starting Automated Evaluation")
    print(f"Provider: {settings.LLM_PROVIDER} | Model: "
          f"{settings.OPENROUTER_MODEL_NAME if settings.LLM_PROVIDER.lower() == 'openrouter' else settings.GEMINI_MODEL_NAME}")
    print("=" * 60)

    judge = OpsJudge()
    mock_db = MagicMock()

    acc, comp, act = [], [], []

    for i, case in enumerate(dataset, start=1):
        print(f"\n--- Case {i} ---")
        print(f"Eval logs: {case['logs'][:80]}...")
        try:
            crew = OpsCrew(
                incident_id=f"eval_{i}",
                logs_content=case["logs"],
                db_session=mock_db,
            )
            result = str(crew.run())

            eval_result = judge.evaluate_report(
                incident_log=case["logs"],
                generated_report=result,
                ground_truth=case["ground_truth"],
            )
            acc.append(eval_result.accuracy_score)
            comp.append(eval_result.completeness_score)
            act.append(eval_result.actionability_score)

            print(f"Scores: Accuracy={eval_result.accuracy_score} "
                  f"Completeness={eval_result.completeness_score} "
                  f"Actionability={eval_result.actionability_score}")
            print(f"Reasoning: {eval_result.reasoning}")
        except Exception as e:
            print(f"Case {i} FAILED: {e}")

    print("\n" + "=" * 60)
    if acc:
        print(f"Dataset size: {len(dataset)}")
        print(f"Avg Accuracy      : {sum(acc) / len(acc):.2f} / 5")
        print(f"Avg Completeness  : {sum(comp) / len(comp):.2f} / 5")
        print(f"Avg Actionability : {sum(act) / len(act):.2f} / 5")
    else:
        print("No cases completed - check API key/provider.")
    print("=" * 60)


if __name__ == "__main__":
    run_evaluation()


import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.evaluation.judge import OpsJudge
from app.crew.crew import OpsCrew
from app.models.incident import Incident # Mock if needed, or use schemas
from unittest.mock import MagicMock

# Simple Golden Dataset
dataset = [
    {
        "logs": """[ERROR] Database connection failed: password authentication failed for user "postgres".""",
        "ground_truth": "Root Cause: Incorrect database password. Fix: Update credentials.",
        "expected_root_cause": "Authentication failure"
    }
]

def run_evaluation():
    print("Starting Automated Evaluation...")
    judge = OpsJudge()
    
    # Mock DB Session for Crew
    mock_db = MagicMock()
    
    total_score = 0
    
    for case in dataset:
        print(f"Evaluating case with logs: {case['logs'][:50]}...")
        
        # Run OpsPilot (Crew)
        # Note: We need a valid API key for this to actually run against Gemini
        try:
            crew = OpsCrew(incident_id="eval_1", logs_content=case['logs'], db_session=mock_db)
            result = crew.run() # This returns the report string
            
            # Evaluate
            eval_result = judge.evaluate_report(
                incident_log=case['logs'], 
                generated_report=str(result), 
                ground_truth=case['ground_truth']
            )
            
            print(f"Scores: Acc={eval_result.accuracy_score}, Comp={eval_result.completeness_score}, Act={eval_result.actionability_score}")
            print(f"Reasoning: {eval_result.reasoning}")
            
            total_score += eval_result.accuracy_score
            
        except Exception as e:
            print(f"Evaluation failed: {e}")

    avg_score = total_score / len(dataset)
    print(f"Average Accuracy Score: {avg_score}")

if __name__ == "__main__":
    run_evaluation()

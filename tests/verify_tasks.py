import os
from unittest.mock import MagicMock, patch
from app.crew.tasks import OpsTasks
from app.crew.agents import OpsAgents
from crewai import Task

def test_task_context_passing():
    print("Testing Task Context Passing...")
    tasks = OpsTasks()
    agents = OpsAgents()
    
    # Mock agents to avoid LLM calls
    mock_agent = MagicMock()
    
    context_task = Task(description="ctx", expected_output="out", agent=mock_agent)
    
    # Test identify_root_cause_task
    try:
        task = tasks.identify_root_cause_task(mock_agent, [context_task])
        if task.context == [context_task]:
            print("PASS: identify_root_cause_task received context.")
        else:
            print(f"FAIL: identify_root_cause_task missing context. Got {task.context}")
    except TypeError as e:
        print(f"FAIL: identify_root_cause_task raised TypeError: {e}")

    # Test suggest_fix_task
    try:
        task = tasks.suggest_fix_task(mock_agent, [context_task])
        if task.context == [context_task]:
            print("PASS: suggest_fix_task received context.")
        else:
            print(f"FAIL: suggest_fix_task missing context. Got {task.context}")
    except TypeError as e:
        print(f"FAIL: suggest_fix_task raised TypeError: {e}")

if __name__ == "__main__":
    test_task_context_passing()

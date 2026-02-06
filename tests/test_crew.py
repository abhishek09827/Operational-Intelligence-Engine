import pytest
from unittest.mock import MagicMock, patch
from app.crew.crew import OpsCrew

@patch('app.crew.agents.ChatGoogleGenerativeAI')
def test_crew_initialization(mock_llm):
    # Mock LLM to avoid API calls and key errors during test
    mock_llm.return_value = MagicMock()
    
    crew = OpsCrew(incident_id="inc-123", logs_content="Error: adapter not found")
    
    assert crew.incident_id == "inc-123"
    assert crew.logs_content == "Error: adapter not found"
    assert crew.agents is not None
    assert crew.tasks is not None

@patch('app.crew.crew.Crew')
@patch('app.crew.agents.ChatGoogleGenerativeAI')
def test_crew_run_structure(mock_llm, mock_crew_class):
    # Mock dependencies
    mock_llm.return_value = MagicMock()
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = "Report generated"
    mock_crew_class.return_value = mock_crew_instance
    
    crew = OpsCrew(incident_id="inc-123", logs_content="Error: Something failed")
    result = crew.run()
    
    assert result == "Report generated"
    # Verify strict sequential process was used
    mock_crew_class.assert_called_once()
    call_kwargs = mock_crew_class.call_args[1]
    assert len(call_kwargs['agents']) == 4
    assert len(call_kwargs['tasks']) == 4

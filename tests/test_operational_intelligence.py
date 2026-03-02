"""
Test suite for the Operational Intelligence Engine
Tests the new log schema, validation logic, and AI-powered analysis
"""

import json
import pytest
from app.schemas.log_analysis import (
    LogCategory, Severity, HttpMethod, PaymentMethod, FailureReason,
    AnalysisEntry, AnalysisSummary, OperationalIntelligenceOutput,
    EXAMPLE_LOG_ENTRIES,
    validate_llm_output,
    check_hallucination_risks
)
from app.crew.agents import OpsAgents
from app.crew.tasks import OpsTasks


class TestLogSchema:
    """Test the log schema definitions"""
    
    def test_log_category_enum(self):
        """Test log category enum values"""
        assert LogCategory.API_ERROR.value == "API_ERROR"
        assert LogCategory.PAYMENT_FAILURE.value == "PAYMENT_FAILURE"
        assert LogCategory.TIMEOUT.value == "TIMEOUT"
        assert LogCategory.RATE_LIMIT.value == "RATE_LIMIT"
        assert LogCategory.DEPENDENCY_DOWN.value == "DEPENDENCY_DOWN"
    
    def test_severity_enum(self):
        """Test severity enum values"""
        assert Severity.CRITICAL.value == "CRITICAL"
        assert Severity.HIGH.value == "HIGH"
        assert Severity.MEDIUM.value == "MEDIUM"
        assert Severity.LOW.value == "LOW"
    
    def test_api_error_fields(self):
        """Test API error fields structure"""
        agent = OpsAgents()
        api_agent = agent.api_error_agent()
        assert api_agent is not None
    
    def test_payment_failure_fields(self):
        """Test payment failure fields structure"""
        agent = OpsAgents()
        payment_agent = agent.payment_failure_agent()
        assert payment_agent is not None
    
    def test_timeout_fields(self):
        """Test timeout fields structure"""
        agent = OpsAgents()
        timeout_agent = agent.timeout_agent()
        assert timeout_agent is not None


class TestValidationLogic:
    """Test the validation logic layer"""
    
    def test_validate_valid_json(self):
        """Test validation of valid JSON output"""
        valid_json = json.dumps({
            "analysis": [
                {
                    "log_id": "test-1",
                    "category": "API_ERROR",
                    "severity": "HIGH",
                    "root_cause": "Database connection pool exhausted",
                    "detailed_explanation": "POST /api/v1/orders/create returned 500 due to 50 open connections exceeding pool limit of 48",
                    "recommended_fix": "Increase database connection pool size to 80 or optimize queries to reduce connections",
                    "prevention_strategy": "Implement connection pool monitoring and auto-scaling based on active connections",
                    "confidence_score": 0.95,
                    "is_recurrent_pattern": True,
                    "affected_services": ["order-service"],
                    "suggested_monitoring": ["db_connections_active", "db_connection_pool_usage"]
                }
            ],
            "summary": {
                "total_errors": 1,
                "high_severity_count": 1,
                "most_common_category": "API_ERROR",
                "recommendations": ["Monitor database connections"]
            }
        })
        
        result = validate_llm_output(valid_json)
        assert isinstance(result, OperationalIntelligenceOutput)
        assert len(result.analysis) == 1
    
    def test_validate_invalid_json(self):
        """Test validation of invalid JSON"""
        invalid_json = "This is not valid JSON {"
        
        with pytest.raises(ValueError, match="Invalid JSON format"):
            validate_llm_output(invalid_json)
    
    def test_validate_missing_fields(self):
        """Test validation with missing required fields"""
        invalid_json = json.dumps({
            "analysis": [
                {
                    "log_id": "test-1",
                    # Missing category, severity, etc.
                    "root_cause": "Test cause"
                }
            ]
        })
        
        with pytest.raises(Exception):  # Will fail during parsing/validation
            validate_llm_output(invalid_json)
    
    def test_validate_confidence_requirement(self):
        """Test that low confidence requires 'uncertain' in explanation"""
        invalid_json = json.dumps({
            "analysis": [
                {
                    "log_id": "test-1",
                    "category": "API_ERROR",
                    "severity": "HIGH",
                    "root_cause": "Test cause",
                    "detailed_explanation": "This is uncertain but confidence is low",  # Should have "uncertain"
                    "recommended_fix": "Test fix",
                    "prevention_strategy": "Test prevention",
                    "confidence_score": 0.5,
                    "is_recurrent_pattern": False,
                    "affected_services": [],
                    "suggested_monitoring": []
                }
            ],
            "summary": {
                "total_errors": 1,
                "high_severity_count": 1,
                "most_common_category": "API_ERROR",
                "recommendations": []
            }
        })
        
        # This should fail because low confidence doesn't have "uncertain"
        with pytest.raises(ValueError):
            validate_llm_output(invalid_json)
    
    def test_check_hallucination_risks(self):
        """Test hallucination risk detection"""
        valid_analysis = {
            "log_id": "550e8400-e29b-41d4-a716-446655440000",
            "category": "API_ERROR",
            "severity": "HIGH",
            "root_cause": "Database connection pool exhausted",
            "detailed_explanation": "POST /api/v1/orders/create returned 500 due to 50 open connections exceeding pool limit of 48",
            "recommended_fix": "Increase database connection pool size to 80 or optimize queries to reduce connections",
            "prevention_strategy": "Implement connection pool monitoring and auto-scaling based on active connections",
            "confidence_score": 0.95,
            "is_recurrent_pattern": True,
            "affected_services": ["order-service"],
            "suggested_monitoring": ["db_connections_active", "db_connection_pool_usage"]
        }
        
        risks = check_hallucination_risks(valid_analysis)
        assert risks['is_valid'] == True
        assert len(risks['warnings']) == 0
        assert len(risks['critical_failures']) == 0
    
    def test_check_hallucination_risks_vague_root_cause(self):
        """Test detection of vague root causes"""
        invalid_analysis = {
            "log_id": "test-1",
            "category": "API_ERROR",
            "severity": "HIGH",
            "root_cause": "System error",  # Too vague
            "detailed_explanation": "Something went wrong",
            "recommended_fix": "Fix it",
            "prevention_strategy": "Prevent it",
            "confidence_score": 0.8,
            "is_recurrent_pattern": False,
            "affected_services": [],
            "suggested_monitoring": []
        }
        
        risks = check_hallucination_risks(invalid_analysis)
        assert risks['is_valid'] == False
        assert len(risks['critical_failures']) > 0
        assert "too vague" in risks['critical_failures'][0].lower()


class TestCrewAgents:
    """Test the specialized crew agents"""
    
    def test_agents_initialization(self):
        """Test that all agents are initialized correctly"""
        agent = OpsAgents()
        
        assert agent.api_error_agent() is not None
        assert agent.payment_failure_agent() is not None
        assert agent.timeout_agent() is not None
        assert agent.rate_limit_agent() is not None
        assert agent.dependency_agent() is not None
        assert agent.validation_agent() is not None
        assert agent.report_generator_agent() is not None
    
    def test_agent_specialization(self):
        """Test that agents have appropriate backstories"""
        agent = OpsAgents()
        
        api_agent = agent.api_error_agent()
        assert "API" in api_agent.backstory
        assert "400" in api_agent.backstory or "500" in api_agent.backstory
        
        payment_agent = agent.payment_failure_agent()
        assert "payment" in payment_agent.backstory.lower()
        assert "transaction" in payment_agent.backstory.lower()


class TestOpsTasks:
    """Test the crew tasks"""
    
    def test_prompt_template_creation(self):
        """Test that prompt template is created correctly"""
        tasks = OpsTasks()
        prompt = tasks.create_prompt_template()
        
        assert prompt is not None
        assert "API error patterns" in prompt
        assert "PAYMENT_FAILURE" in prompt
        assert "TIMEOUT" in prompt
        assert "JSON schema" in prompt
    
    def test_analyze_logs_task(self):
        """Test log analysis task creation"""
        tasks = OpsTasks()
        agent = OpsAgents().api_error_agent()
        
        task = tasks.analyze_logs_task(agent, "Sample log content")
        
        assert task is not None
        assert agent in task.agent
        assert "Sample log content" in task.description
    
    def test_validate_output_task(self):
        """Test output validation task creation"""
        tasks = OpsTasks()
        agent = OpsAgents().validation_agent()
        
        test_json = '{"analysis": []}'
        task = tasks.validate_output_task(agent, test_json)
        
        assert task is not None
        assert agent in task.agent
        assert test_json in task.description
    
    def test_generate_report_task(self):
        """Test report generation task creation"""
        tasks = OpsTasks()
        agent = OpsAgents().report_generator_agent()
        
        test_analysis = '{"analysis": [], "summary": {}}'
        task = tasks.generate_report_task(agent, test_analysis)
        
        assert task is not None
        assert agent in task.agent
        assert test_analysis in task.description


class TestIntegration:
    """Integration tests for the complete workflow"""
    
    def test_full_workflow_with_examples(self):
        """Test the full workflow using example log entries"""
        # Load example log entries
        example_logs = json.dumps(EXAMPLE_LOG_ENTRIES)
        
        # Create agents and tasks
        agent = OpsAgents()
        tasks = OpsTasks()
        
        # Create tasks
        analysis_task = tasks.analyze_logs_task(agent.api_error_agent(), example_logs)
        validation_task = tasks.validate_output_task(agent.validation_agent(), "{placeholder}")
        
        # Verify task setup
        assert analysis_task is not None
        assert validation_task is not None
        
        # Verify prompt contains required sections
        prompt = tasks.create_prompt_template()
        assert "Few-Shot Examples" in prompt
        assert "Validation Rules" in prompt
        assert "Output Schema" in prompt
    
    def test_all_log_categories_present(self):
        """Test that all log categories are defined and documented"""
        agent = OpsAgents()
        tasks = OpsTasks()
        
        prompt = tasks.create_prompt_template()
        
        # Verify all categories are mentioned
        for category in LogCategory:
            assert category.value in prompt or category.value.lower() in prompt.lower()


class TestRealisticScenarios:
    """Test with realistic log scenarios"""
    
    def test_api_error_scenario(self):
        """Test API error analysis scenario"""
        api_log = {
            "log_id": "550e8400-e29b-41d4-a716-446655440000",
            "timestamp": "2024-03-01T14:30:22.123Z",
            "level": "ERROR",
            "category": "API_ERROR",
            "service_name": "order-service",
            "environment": "production",
            "request_id": "req_12345",
            "api_error": {
                "method": "POST",
                "endpoint": "/api/v1/orders/create",
                "http_status": 500,
                "error_code": "INTERNAL_SERVER_ERROR",
                "client_ip": "192.168.1.100",
                "user_agent": "Mozilla/5.0"
            },
            "error_message": "Database connection timeout while inserting order record",
            "stack_trace": "Error: Connection timeout\n    at OrderService.createOrder (order-service.js:245:10)\n    at /app/index.js:89:22"
        }
        
        risks = check_hallucination_risks(api_log)
        assert "API_ERROR" in risks.get('warnings', [])
    
    def test_payment_failure_scenario(self):
        """Test payment failure analysis scenario"""
        payment_log = {
            "log_id": "660e8400-e29b-41d4-a716-446655440001",
            "timestamp": "2024-03-01T14:31:15.456Z",
            "level": "ERROR",
            "category": "PAYMENT_FAILURE",
            "service_name": "payment-service",
            "environment": "production",
            "request_id": "req_67890",
            "payment_failure": {
                "transaction_id": "txn_abc123xyz",
                "amount": 299.99,
                "currency": "USD",
                "payment_method": "credit_card",
                "failure_reason": "insufficient_funds",
                "raw_response": "Declined: Insufficient funds (Transaction #txn_abc123xyz)"
            },
            "error_message": "Payment processing failed due to insufficient account balance"
        }
        
        risks = check_hallucination_risks(payment_log)
        assert "PAYMENT_FAILURE" in risks.get('warnings', [])
    
    def test_timeout_scenario(self):
        """Test timeout analysis scenario"""
        timeout_log = {
            "log_id": "770e8400-e29b-41d4-a716-446655440002",
            "timestamp": "2024-03-01T14:32:10.789Z",
            "level": "ERROR",
            "category": "TIMEOUT",
            "service_name": "inventory-service",
            "environment": "production",
            "request_id": "req_99999",
            "timeout": {
                "operation": "get_inventory_level",
                "timeout_ms": 5000,
                "retry_count": 3,
                "last_retry_attempt": "2024-03-01T14:32:05.678Z",
                "original_timeout": "2024-03-01T14:32:05.678Z"
            },
            "error_message": "Operation exceeded 5000ms timeout after 3 retry attempts"
        }
        
        risks = check_hallucination_risks(timeout_log)
        assert "TIMEOUT" in risks.get('warnings', [])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
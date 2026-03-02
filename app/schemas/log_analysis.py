"""
Schema definitions for Operational Intelligence Engine log analysis.
Focuses on error monitoring and incident response patterns.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Optional, Dict, Any
from enum import Enum


class LogLevel(str, Enum):
    ERROR = "ERROR"
    WARN = "WARN"
    INFO = "INFO"


class LogCategory(str, Enum):
    API_ERROR = "API_ERROR"
    PAYMENT_FAILURE = "PAYMENT_FAILURE"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    DEPENDENCY_DOWN = "DEPENDENCY_DOWN"


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"
    PATCH = "PATCH"


class PaymentMethod(str, Enum):
    CREDIT_CARD = "credit_card"
    PAYPAL = "paypal"
    STRIPE = "stripe"


class FailureReason(str, Enum):
    DECLINED = "declined"
    EXPIRED = "expired"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    INVALID_CARD = "invalid_card"
    GENERAL_FAILURE = "general_failure"


class ApiErrorFields(BaseModel):
    """Fields for API error log entries"""
    method: HttpMethod
    endpoint: str
    http_status: int = Field(ge=400, le=599, description="HTTP status code")
    error_code: str
    client_ip: str
    user_agent: str


class PaymentFailureFields(BaseModel):
    """Fields for payment failure log entries"""
    transaction_id: str
    amount: float = Field(ge=0, description="Transaction amount")
    currency: Literal["USD", "EUR", "GBP", "INR", "CAD", "AUD"]
    payment_method: PaymentMethod
    failure_reason: FailureReason
    raw_response: str


class TimeoutFields(BaseModel):
    """Fields for timeout log entries"""
    operation: str
    timeout_ms: int = Field(ge=100, description="Timeout in milliseconds")
    retry_count: int = Field(ge=0, description="Number of retry attempts")
    last_retry_attempt: str  # ISO-8601 format
    original_timeout: str  # ISO-8601 format


class RateLimitFields(BaseModel):
    """Fields for rate limit violation log entries"""
    limit: int = Field(ge=1, description="Rate limit per time period")
    remaining: int = Field(ge=0, description="Remaining requests")
    reset_at: str  # ISO-8601 format
    path: str


class DependencyFailureFields(BaseModel):
    """Fields for downstream dependency failure log entries"""
    dependency_name: str
    error_type: str  # e.g., "503", "504", "connection_timeout"
    affected_services: List[str]
    retry_strategy: str


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AnalysisEntry(BaseModel):
    """Structured analysis entry for a single log"""
    log_id: str
    category: LogCategory
    severity: Severity
    root_cause: str = Field(max_length=200, description="Specific root cause")
    detailed_explanation: str = Field(max_length=500, description="Detailed analysis")
    recommended_fix: str = Field(max_length=300, description="Actionable fix")
    prevention_strategy: str = Field(max_length=300, description="Long-term prevention")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Confidence in analysis")
    is_recurrent_pattern: bool
    affected_services: List[str] = Field(default_factory=list)
    suggested_monitoring: List[str] = Field(default_factory=list)
    
    @field_validator('confidence_score')
    @classmethod
    def validate_confidence(cls, v, values):
        """Low confidence must include 'uncertain' in explanation"""
        if v < 0.7:
            explanation = values.get('detailed_explanation', '')
            if 'uncertain' not in explanation.lower():
                raise ValueError(
                    'Low confidence (<0.7) must include "uncertain" in detailed_explanation'
                )
        return v


class AnalysisSummary(BaseModel):
    """Summary of all analyzed logs"""
    total_errors: int
    high_severity_count: int
    most_common_category: LogCategory
    recommendations: List[str]


class OperationalIntelligenceOutput(BaseModel):
    """Complete output from the operational intelligence engine"""
    analysis: List[AnalysisEntry]
    summary: AnalysisSummary


# Mock/Example log entries for testing
EXAMPLE_LOG_ENTRIES = [
    {
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
    },
    {
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
]


def validate_llm_output(llm_output: str) -> OperationalIntelligenceOutput:
    """
    Validate LLM output against strict schema
    
    Args:
        llm_output: JSON string containing the LLM analysis
        
    Returns:
        Parsed and validated OperationalIntelligenceOutput
        
    Raises:
        ValueError: If validation fails
    """
    import json
    
    try:
        parsed = json.loads(llm_output)
        return OperationalIntelligenceOutput(**parsed)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")
    except Exception as e:
        raise ValueError(f"Validation failed: {e}")


def check_hallucination_risks(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Detect potential hallucinations in LLM output
    
    Args:
        analysis: Dictionary containing the analysis data
        
    Returns:
        Dictionary with validation status and warnings
    """
    risks = {
        'is_valid': True,
        'warnings': [],
        'critical_failures': []
    }
    
    # Check 1: Root cause is too generic
    if len(analysis.get('root_cause', '')) < 10:
        risks['critical_failures'].append("Root cause too vague - must be specific")
    
    # Check 2: Confident but explanation uncertain
    confidence = analysis.get('confidence_score', 1.0)
    explanation = analysis.get('detailed_explanation', '')
    if confidence < 0.7:
        if 'uncertain' not in explanation.lower():
            risks['warnings'].append("Low confidence requires 'uncertain' in explanation")
    
    # Check 3: Fix doesn't address root cause
    fix = analysis.get('recommended_fix', '')
    if fix in ["Investigate further", "Review logs", "Not applicable"]:
        risks['critical_failures'].append("Fix must be actionable, not vague")
    
    # Check 4: Affected services don't match log
    affected = set(analysis.get('affected_services', []))
    # Extract service name from log_id (simple heuristic)
    log_id = analysis.get('log_id', '')
    if log_id:
        service_name = log_id.split('_')[0] if '_' in log_id else log_id
        if service_name and service_name not in affected:
            risks['warnings'].append(f"Log service {service_name} not in affected services")
    
    # Check 5: Missing prevention strategy
    prevention = analysis.get('prevention_strategy', '')
    if not prevention or prevention.startswith('TODO') or prevention == "None":
        risks['warnings'].append("Missing or vague prevention strategy")
    
    # Check 6: Confidence score outside valid range
    if not (0.0 <= confidence <= 1.0):
        risks['critical_failures'].append(f"Invalid confidence score: {confidence}")
    
    # Check 7: Category mismatch
    category = analysis.get('category', '')
    if category not in [e.value for e in LogCategory]:
        risks['critical_failures'].append(f"Invalid category: {category}")
    
    if risks['critical_failures']:
        risks['is_valid'] = False
    
    return risks
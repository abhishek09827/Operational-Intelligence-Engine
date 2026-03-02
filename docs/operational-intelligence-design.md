# Operational Intelligence Engine - Design Document

## Focus Areas

The system now focuses specifically on:
1. HTTP API error logs (4xx, 5xx)
2. Payment/transaction failure logs
3. Timeout and retry patterns
4. Rate limit violations
5. Downstream dependency failures

## 1. Log Schema Design

### Structure: `LogEntry` (JSON format)

```json
{
  "log_id": "uuid",
  "timestamp": "ISO-8601 string",
  "level": "ERROR | WARN | INFO",
  "category": "API_ERROR | PAYMENT_FAILURE | TIMEOUT | RATE_LIMIT | DEPENDENCY_DOWN",
  
  // Common fields
  "service_name": "string",
  "environment": "string",
  "request_id": "string (optional)",
  
  // Category-specific fields
  "api_error": {
    "method": "GET | POST | PUT | DELETE | PATCH",
    "endpoint": "/api/v1/resource",
    "http_status": 500,
    "error_code": "INTERNAL_SERVER_ERROR",
    "client_ip": "string",
    "user_agent": "string"
  },
  
  "payment_failure": {
    "transaction_id": "string",
    "amount": "decimal",
    "currency": "USD",
    "payment_method": "credit_card | paypal | stripe",
    "failure_reason": "declined | expired | insufficient_funds",
    "raw_response": "string"
  },
  
  "timeout": {
    "operation": "string",
    "timeout_ms": 1000,
    "retry_count": 3,
    "last_retry_attempt": "ISO-8601 string",
    "original_timeout": "ISO-8601 string"
  },
  
  "rate_limit": {
    "limit": 1000,
    "remaining": 0,
    "reset_at": "ISO-8601 string",
    "path": "/api/v1/high-load-endpoint"
  },
  
  "dependency_failure": {
    "dependency_name": "payment_service | user_service | database",
    "error_type": "connection_timeout | 503 | 504",
    "affected_services": ["checkout", "billing"],
    "retry_strategy": "exponential_backoff"
  },
  
  // Additional context
  "error_message": "string",
  "stack_trace": "string (optional)",
  "metadata": {
    "additional_field": "value"
  }
}
```

## 2. Example Log Entries

### Example 1: HTTP 5xx API Error
```json
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
}
```

### Example 2: Payment Transaction Failure
```json
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
```

### Example 3: Timeout and Retry Pattern
```json
{
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
```

### Example 4: Rate Limit Violation
```json
{
  "log_id": "880e8400-e29b-41d4-a716-446655440003",
  "timestamp": "2024-03-01T14:33:05.012Z",
  "level": "ERROR",
  "category": "RATE_LIMIT",
  "service_name": "api-gateway",
  "environment": "production",
  "request_id": "req_00001",
  "rate_limit": {
    "limit": 1000,
    "remaining": 0,
    "reset_at": "2024-03-01T15:00:00.000Z",
    "path": "/api/v1/reports/generate"
  },
  "error_message": "Rate limit exceeded for endpoint /api/v1/reports/generate"
}
```

### Example 5: Downstream Dependency Failure
```json
{
  "log_id": "990e8400-e29b-41d4-a716-446655440004",
  "timestamp": "2024-03-01T14:34:20.345Z",
  "level": "ERROR",
  "category": "DEPENDENCY_DOWN",
  "service_name": "checkout-service",
  "environment": "production",
  "request_id": "req_11111",
  "dependency_failure": {
    "dependency_name": "payment_service",
    "error_type": "503",
    "affected_services": ["checkout", "billing"],
    "retry_strategy": "exponential_backoff"
  },
  "error_message": "Downstream service payment_service unavailable (503 Service Unavailable)"
}
```

## 3. AI Prompt Template

### Optimization Strategy
- Use few-shot learning with example log entries
- Strict JSON schema enforcement
- Category-specific guidance for each log type
- Clear validation rules and constraints
- Role-play with domain expertise

### Prompt Template

```
You are an expert Production Operations Analyst specializing in error monitoring and incident response. Your domain expertise includes:

- API error patterns (4xx, 5xx HTTP status codes)
- Payment and transaction failure analysis
- Distributed system timeouts and retry patterns
- Rate limiting and throttling violations
- Downstream dependency failures and circuit breakers

## Task
Analyze the following log entries and provide structured operational intelligence.

## Input Log Entries
{log_entries}

## Your Analysis Requirements

For each log entry, analyze:
1. **Error Pattern**: Identify the specific failure mode
2. **Severity**: Determine impact (Critical, High, Medium, Low)
3. **Root Cause**: Explain why the error occurred
4. **Recommendations**: Provide actionable fixes
5. **Prevention**: Suggest system improvements to prevent recurrence

## Output Schema (Strict JSON Format)
```json
{
  "analysis": [
    {
      "log_id": "uuid",
      "category": "API_ERROR | PAYMENT_FAILURE | TIMEOUT | RATE_LIMIT | DEPENDENCY_DOWN",
      "severity": "CRITICAL | HIGH | MEDIUM | LOW",
      "root_cause": "string (max 200 chars)",
      "detailed_explanation": "string (max 500 chars)",
      "recommended_fix": "string (max 300 chars)",
      "prevention_strategy": "string (max 300 chars)",
      "confidence_score": 0.0-1.0,
      "is_recurrent_pattern": boolean,
      "affected_services": ["array of strings"],
      "suggested_monitoring": "array of metrics to track"
    }
  ],
  "summary": {
    "total_errors": integer,
    "high_severity_count": integer,
    "most_common_category": string,
    "recommendations": ["array of general recommendations"]
  }
}
```

## Constraints & Guidelines

1. **JSON Schema Compliance**: Output MUST be valid JSON
2. **Strict Typing**: All values must match specified types
3. **Severity Thresholds**:
   - CRITICAL: System down, data loss, or security breach
   - HIGH: Critical functionality degraded
   - MEDIUM: Partial degradation
   - LOW: Performance issues, non-critical errors

4. **Root Cause Quality**: Be specific, not generic. Avoid "unknown" or "system error"
5. **Fixes Must Be Actionable**: Include specific steps, not vague suggestions
6. **Confidence Score**: Only claim high confidence if you're certain
7. **Prevention**: Focus on long-term improvements, not just fixes

## Few-Shot Examples

### Example 1: API Error Analysis
```json
{
  "log_id": "550e8400-e29b-41d4-a716-446655440000",
  "category": "API_ERROR",
  "severity": "HIGH",
  "root_cause": "Database connection pool exhausted",
  "detailed_explanation": "POST /api/v1/orders/create returned 500 due to 50 open connections exceeding pool limit of 48",
  "recommended_fix": "Increase database connection pool size to 80 or optimize queries to reduce connections",
  "prevention_strategy": "Implement connection pool monitoring and auto-scaling based on active connections",
  "confidence_score": 0.95,
  "is_recurrent_pattern": true,
  "affected_services": ["order-service"],
  "suggested_monitoring": ["db_connections_active", "db_connection_pool_usage", "order_creation_latency"]
}
```

### Example 2: Payment Failure Analysis
```json
{
  "log_id": "660e8400-e29b-41d4-a716-446655440001",
  "category": "PAYMENT_FAILURE",
  "severity": "CRITICAL",
  "root_cause": "Payment gateway returned insufficient funds",
  "detailed_explanation": "Transaction txn_abc123xyz declined due to user account balance below required $299.99",
  "recommended_fix": "Implement account balance validation before order creation, show error to user immediately",
  "prevention_strategy": "Add pre-order payment validation endpoint to catch this before processing",
  "confidence_score": 1.0,
  "is_recurrent_pattern": false,
  "affected_services": ["payment-service", "checkout-service"],
  "suggested_monitoring": ["payment_decline_rate", "payment_success_rate", "transaction_failures"]
}
```

### Example 3: Timeout Analysis
```json
{
  "log_id": "770e8400-e29b-41d4-a716-446655440002",
  "category": "TIMEOUT",
  "severity": "HIGH",
  "root_cause": "Third-party inventory service response time exceeded configured 5000ms",
  "detailed_explanation": "get_inventory_level operation timed out after 5000ms and 3 retry attempts. Customer waiting 15s total",
  "recommended_fix": "Implement circuit breaker pattern for inventory service and cache frequently accessed inventory levels",
  "prevention_strategy": "Set shorter timeout (2s) with retry, implement local cache for hot items",
  "confidence_score": 0.92,
  "is_recurrent_pattern": true,
  "affected_services": ["checkout-service", "inventory-service"],
  "suggested_monitoring": ["inventory_service_latency_p95", "checkout_page_load_time", "circuit_breaker_status"]
}
```

### Example 4: Rate Limit Analysis
```json
{
  "log_id": "880e8400-e29b-41d4-a716-446655440003",
  "category": "RATE_LIMIT",
  "severity": "MEDIUM",
  "root_cause": "Bulk report generation endpoint rate limited to 1000 req/hr, hit limit at 14:33:05",
  "detailed_explanation": "User generated 200 requests in 10 minutes, exceeding 1000/hour limit for /api/v1/reports/generate",
  "recommended_fix": "Implement rate limit warnings at 80% usage, suggest batching for large exports",
  "prevention_strategy": "Add quota limits per user and notify before hitting rate limit",
  "confidence_score": 0.98,
  "is_recurrent_pattern": true,
  "affected_services": ["api-gateway"],
  "suggested_monitoring": ["rate_limit_exceeded_total", "rate_limit_by_endpoint", "user_quota_usage"]
}
```

### Example 5: Dependency Failure Analysis
```json
{
  "log_id": "990e8400-e29b-41d4-a716-446655440004",
  "category": "DEPENDENCY_DOWN",
  "severity": "CRITICAL",
  "root_cause": "payment_service returned 503 after 5 consecutive 502 errors",
  "detailed_explanation": "Circuit breaker opened on payment_service, checkout flow blocked for all users",
  "recommended_fix": "Enable immediate fallback to payment service with backup credit card processors",
  "prevention_strategy": "Implement multi-provider payment routing and automatic failover",
  "confidence_score": 1.0,
  "is_recurrent_pattern": false,
  "affected_services": ["checkout-service", "payment-service", "billing-service"],
  "suggested_monitoring": ["payment_service_health_status", "circuit_breaker_state", "checkout_flow_completion_rate"]
}
```

## Validation Rules

- Each analysis entry MUST contain all required fields
- Severity must be one of: CRITICAL, HIGH, MEDIUM, LOW
- Confidence score must be 0.0-1.0 (1 decimal place)
- Categories must be one of: API_ERROR, PAYMENT_FAILURE, TIMEOUT, RATE_LIMIT, DEPENDENCY_DOWN
- All string fields should be concise (max character limits)
- Confidence score < 0.7 must be accompanied by "uncertain" in explanation

Now, analyze the input log entries and provide the strict JSON output as required.
```

## 4. Validation Logic Layer

### Schema Validation (Python Implementation)

```python
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Literal
from uuid import UUID

class ApiErrorFields(BaseModel):
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"]
    endpoint: str
    http_status: int = Field(ge=400, le=599)
    error_code: str
    client_ip: str
    user_agent: str

class PaymentFailureFields(BaseModel):
    transaction_id: str
    amount: float = Field(ge=0)
    currency: Literal["USD", "EUR", "GBP", "INR", "CAD", "AUD"]
    payment_method: Literal["credit_card", "paypal", "stripe"]
    failure_reason: str
    raw_response: str

class TimeoutFields(BaseModel):
    operation: str
    timeout_ms: int = Field(ge=100)
    retry_count: int = Field(ge=0)
    last_retry_attempt: str
    original_timeout: str

class RateLimitFields(BaseModel):
    limit: int = Field(ge=1)
    remaining: int = Field(ge=0)
    reset_at: str
    path: str

class DependencyFailureFields(BaseModel):
    dependency_name: str
    error_type: str
    affected_services: List[str]
    retry_strategy: str

class AnalysisEntry(BaseModel):
    log_id: str
    category: Literal["API_ERROR", "PAYMENT_FAILURE", "TIMEOUT", "RATE_LIMIT", "DEPENDENCY_DOWN"]
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    root_cause: str = Field(max_length=200)
    detailed_explanation: str = Field(max_length=500)
    recommended_fix: str = Field(max_length=300)
    prevention_strategy: str = Field(max_length=300)
    confidence_score: float = Field(ge=0.0, le=1.0)
    is_recurrent_pattern: bool
    affected_services: List[str] = []
    suggested_monitoring: List[str] = []
    
    @validator('confidence_score')
    def validate_confidence(cls, v, values):
        if v < 0.7:
            if not v.lower().startswith('uncertain'):
                raise ValueError('Low confidence must include "uncertain" in explanation')
        return v

class AnalysisSummary(BaseModel):
    total_errors: int
    high_severity_count: int
    most_common_category: str
    recommendations: List[str]

class OperationalIntelligenceOutput(BaseModel):
    analysis: List[AnalysisEntry]
    summary: AnalysisSummary

def validate_llm_output(llm_output: str) -> OperationalIntelligenceOutput:
    """Validate LLM output against strict schema"""
    try:
        parsed = json.loads(llm_output)
        return OperationalIntelligenceOutput(**parsed)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")
    except Exception as e:
        raise ValueError(f"Validation failed: {e}")

def validate_category_specific_fields(log_data: Dict[str, Any]) -> bool:
    """Validate category-specific fields based on log type"""
    category = log_data.get('category')
    
    if category == 'API_ERROR':
        required = ['api_error', 'api_error.endpoint', 'api_error.http_status']
        return all(log_data.get(field) for field in required)
    
    elif category == 'PAYMENT_FAILURE':
        required = ['payment_failure', 'payment_failure.transaction_id']
        return all(log_data.get(field) for field in required)
    
    elif category == 'TIMEOUT':
        required = ['timeout', 'timeout.operation']
        return all(log_data.get(field) for field in required)
    
    elif category == 'RATE_LIMIT':
        required = ['rate_limit', 'rate_limit.limit']
        return all(log_data.get(field) for field in required)
    
    elif category == 'DEPENDENCY_DOWN':
        required = ['dependency_failure', 'dependency_failure.dependency_name']
        return all(log_data.get(field) for field in required)
    
    return True
```

## 5. Guardrails to Prevent Hallucinations

### Guardrail Implementation

1. **Few-Shot Examples**: Provide real examples from similar log patterns
2. **Category Restriction**: Force model to categorize logs into allowed types
3. **Strict Type Enforcement**: JSON schema validation with type checking
4. **Confidence Thresholds**: Require minimum confidence for critical claims
5. **Constraint Checkers**: Validate all fields against defined constraints
6. **Explanation Quality**: Require detailed, specific explanations
7. **Prevention Focus**: Ensure recommendations include preventive measures
8. **Circuit Breaker**: Reject output that doesn't match schema

### Hallucination Prevention Logic

```python
def check_hallucination_risks(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Detect potential hallucinations in LLM output"""
    risks = {
        'is_valid': True,
        'warnings': [],
        'critical_failures': []
    }
    
    # Check 1: Root cause is too generic
    if len(analysis['root_cause']) < 10:
        risks['critical_failures'].append("Root cause too vague - must be specific")
    
    # Check 2: Confident but explanation uncertain
    if analysis['confidence_score'] < 0.7:
        if 'uncertain' not in analysis['detailed_explanation'].lower():
            risks['warnings'].append("Low confidence requires 'uncertain' in explanation")
    
    # Check 3: Fix doesn't address root cause
    if analysis['recommended_fix'] == "Investigate further" or analysis['recommended_fix'] == "Review logs":
        risks['critical_failures'].append("Fix must be actionable, not vague")
    
    # Check 4: Affected services don't match log
    affected = set(analysis['affected_services'])
    service_name = analysis.get('log_id', '').split('_')[0]  # Extract service from log_id
    if service_name not in affected:
        risks['warnings'].append(f"Log service {service_name} not in affected services")
    
    # Check 5: Missing prevention strategy
    if not analysis.get('prevention_strategy') or analysis['prevention_strategy'].startswith('TODO'):
        risks['warnings'].append("Missing or vague prevention strategy")
    
    if risks['critical_failures']:
        risks['is_valid'] = False
    
    return risks
```

## 6. Integration Points

### Updated Workflow

1. **Log Ingestion**: Logs are ingested with proper schema validation
2. **LLM Processing**: CrewAI agents analyze logs using the optimized prompt
3. **Validation**: Output is validated against strict JSON schema
4. **Guardrail Check**: Hallucination risk assessment
5. **Error Handling**: Reject invalid outputs and retry with different prompts
6. **Storage**: Valid results stored in database with embeddings
7. **Retrieval**: RAG enables similar log pattern search
8. **Reporting**: Generated reports with actionable insights

### CrewAI Agent Updates

- **Specialized Agents**: Create agents focused on each error category
- **Category Knowledge**: Feed domain-specific knowledge to each agent
- **Validation Agent**: Add a validation agent to check outputs
- **Circuit Breaker Agent**: Detect and flag potential hallucinations
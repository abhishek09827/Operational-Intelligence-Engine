# Test Input Examples for Operational Intelligence Engine

## Example Log Entries

The system uses the following realistic log entries as test input data:

### Example 1: API Error Log

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

**What this represents:**
- HTTP 500 error on order creation endpoint
- Database connection timeout
- Service: order-service in production environment
- Timestamp: 2024-03-01T14:30:22.123Z

### Example 2: Payment Failure Log

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

**What this represents:**
- Payment transaction declined due to insufficient funds
- Transaction ID: txn_abc123xyz
- Amount: $299.99 USD
- Payment method: Credit card
- Failure reason: Insufficient funds

### Example 3: Timeout Log

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

**What this represents:**
- Timeout on inventory service
- Operation: get_inventory_level
- Timeout: 5000ms
- Retry attempts: 3
- User waited: 15s total (5000ms * 3)

### Example 4: Rate Limit Log

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

**What this represents:**
- Rate limit violation on report generation endpoint
- Limit: 1000 requests/hour
- Remaining: 0 (hit limit)
- Reset time: 15:00:00
- Path: /api/v1/reports/generate

### Example 5: Dependency Failure Log

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

**What this represents:**
- Downstream service failure
- Payment service unavailable (503)
- Circuit breaker likely triggered
- Affected services: checkout, billing

## Valid Output Schema

The system expects this structured JSON output:

```json
{
  "analysis": [
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
  ],
  "summary": {
    "total_errors": 1,
    "high_severity_count": 1,
    "most_common_category": "API_ERROR",
    "recommendations": ["Monitor database connections", "Scale connection pool dynamically"]
  }
}
```

## Validation Checks

The system validates the output for:

1. **Schema Compliance**: All required fields present
2. **Type Validation**: All values match specified types
3. **Enum Values**: Severity must be CRITICAL/HIGH/MEDIUM/LOW
4. **Confidence Score**: Must be 0.0-1.0
5. **Category**: Must be one of 5 error categories
6. **Hallucination Checks**:
   - Root cause specificity (min 10 chars)
   - Low confidence requires "uncertain" keyword
   - Fix must be actionable
   - Affected services match log service
   - Prevention strategy not generic
   - Valid confidence range
   - Valid category

## How to Use These Examples

1. **Test Input**: Pass these logs to the Crew AI agents
2. **Validation**: System validates output against schema
3. **Hallucination Detection**: 7 checks prevent unrealistic outputs
4. **Report Generation**: Create markdown reports from validated analysis

## Example Use Case

```python
import json
from app.schemas.log_analysis import EXAMPLE_LOG_ENTRIES

# Prepare test input
test_input = json.dumps(EXAMPLE_LOG_ENTRIES)

# Create analysis task
# task = analyze_logs_task(api_error_agent, test_input)

# Process with LLM
# result = task.execute()

# Validate output
# validated = validate_llm_output(result.raw)

# Generate report
# report = generate_report_task(report_agent, validated)
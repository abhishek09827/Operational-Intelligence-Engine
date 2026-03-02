from crewai import Task
from textwrap import dedent

class OpsTasks:
    def create_prompt_template(self):
        """Create the optimized prompt template for operational intelligence"""
        return dedent("""
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

            ## Output Schema (Strict JSON Format - ONLY JSON, NO MARKDOWN)
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
                  "suggested_monitoring": ["array of metrics"]
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

            ## CRITICAL OUTPUT REQUIREMENTS
            1. **OUTPUT MUST BE VALID JSON ONLY** - No markdown, no code blocks, no explanations
            2. **NO NON-EXISTENT FIELDS** - Do NOT include "suggested_fix" or any other fields
            3. **STRICT FIELDS ONLY** - Only include fields in the schema above
            4. **NO MARKDOWN** - Output pure JSON without ```json fences
            5. **ONE ENTRY PER LOG** - Do NOT combine multiple logs into one analysis

            ## Severity Classification Guide (CRITICAL, HIGH, MEDIUM, LOW)

            **CRITICAL (System Unavailable or Major Data Loss)**
            - All services affected (multiple microservices down)
            - Data loss or corruption
            - Security breach or vulnerability
            - Circuit breaker OPEN (system effectively down)
            - 5xx errors blocking user access
            - Complete checkout/payment flow blocked
            - Payment gateway completely down
            - Database unavailable
            - Any error affecting 100% of users

            **HIGH (Critical Functionality Degraded)**
            - Single critical service degraded (e.g., payment service down)
            - 503 errors preventing requests
            - Database pool exhaustion (can't process new requests)
            - Payment decline rate > 10%
            - Single endpoint timing out with 3+ retry attempts
            - Specific critical functionality broken (e.g., checkout, order creation)
            - Revenue-impacting errors

            **MEDIUM (Partial Degradation)**
            - Non-critical endpoint errors
            - Validation errors (4xx) but system still functional
            - Rate limiting (system still works, just throttled)
            - Performance degradation (slower but works)
            - Errors affecting 10-50% of requests
            - Non-critical service timeouts

            **LOW (Performance Issues, Non-Critical)**
            - 429 rate limit errors (system working, just limited)
            - Non-essential functionality errors
            - Minor validation errors
            - Performance issues but service operational
            - Errors affecting <10% of requests

            ## Constraints & Guidelines

            1. **JSON Schema Compliance**: Output MUST be valid JSON
            2. **Strict Typing**: All values must match specified types
            3. **Root Cause Quality**: Be specific, not generic. Avoid "unknown" or "system error"
            4. **Fixes Must Be Actionable**: Include specific steps, not vague suggestions
            5. **Confidence Score**: Only claim high confidence if you're certain
            6. **Prevention**: Focus on long-term improvements, not just fixes

            ## Few-Shot Examples

            ### Example 1: CRITICAL - Database Unavailable
            ```json
            {
              "log_id": "550e8400-e29b-41d4-a716-446655440000",
              "category": "API_ERROR",
              "severity": "CRITICAL",
              "root_cause": "Database connection pool exhausted - system cannot process new requests",
              "detailed_explanation": "POST /api/v1/orders/create returned 500 due to 48/48 connections used. No new orders can be created",
              "recommended_fix": "Immediately scale database connection pool or add new database replicas",
              "prevention_strategy": "Implement auto-scaling based on connection pool usage and set up connection pool health alerts",
              "confidence_score": 1.0,
              "is_recurrent_pattern": true,
              "affected_services": ["order-service", "checkout-service", "payment-service"],
              "suggested_monitoring": ["db_connections_active", "db_connection_pool_usage_percent", "order_creation_rate"]
            }
            ```

            ### Example 2: CRITICAL - Payment Gateway Down
            ```json
            {
              "log_id": "660e8400-e29b-41d4-a716-446655440001",
              "category": "PAYMENT_FAILURE",
              "severity": "CRITICAL",
              "root_cause": "Payment gateway returning 503 after 5 consecutive 502 errors",
              "detailed_explanation": "Circuit breaker opened on payment_service, checkout flow blocked for all users. Revenue flow completely stopped",
              "recommended_fix": "Activate backup payment gateway provider immediately, contact payment gateway support",
              "prevention_strategy": "Implement multi-provider payment routing with automatic failover and circuit breaker with faster recovery",
              "confidence_score": 1.0,
              "is_recurrent_pattern": false,
              "affected_services": ["checkout-service", "payment-service", "billing-service"],
              "suggested_monitoring": ["payment_service_health_status", "circuit_breaker_state", "checkout_flow_completion_rate"]
            }
            ```

            ### Example 3: HIGH - Critical Endpoint Timeout
            ```json
            {
              "log_id": "770e8400-e29b-41d4-a716-446655440002",
              "category": "TIMEOUT",
              "severity": "HIGH",
              "root_cause": "get_inventory_level operation exceeded 5000ms timeout after 3 retry attempts",
              "detailed_explanation": "Customers waiting 15 seconds for checkout to complete. Inventory service bottleneck at 95th percentile",
              "recommended_fix": "Reduce timeout from 5000ms to 2000ms, implement local caching for inventory data",
              "prevention_strategy": "Implement circuit breaker for inventory service and add distributed caching layer",
              "confidence_score": 0.92,
              "is_recurrent_pattern": true,
              "affected_services": ["checkout-service", "inventory-service"],
              "suggested_monitoring": ["inventory_service_latency_p95", "checkout_page_load_time", "abandoned_cart_rate"]
            }
            ```

            ### Example 4: HIGH - Payment Decline Rate Spike
            ```json
            {
              "log_id": "880e8400-e29b-41d4-a716-446655440003",
              "category": "PAYMENT_FAILURE",
              "severity": "HIGH",
              "root_cause": "Credit card processing gateway returned 502 errors",
              "detailed_explanation": "Payment decline rate jumped to 45% (normal is 3-5%). 200 transactions failed in last hour. Revenue impact: $60,000",
              "recommended_fix": "Switch to backup payment processor, monitor declined transactions for chargebacks",
              "prevention_strategy": "Implement dual payment gateway setup with automatic failover",
              "confidence_score": 0.95,
              "is_recurrent_pattern": true,
              "affected_services": ["checkout-service", "payment-service"],
              "suggested_monitoring": ["payment_decline_rate", "payment_success_rate", "transaction_failures_by_code"]
            }
            ```

            ### Example 5: MEDIUM - Validation Error (Non-Critical)
            ```json
            {
              "log_id": "990e8400-e29b-41d4-a716-446655440004",
              "category": "API_ERROR",
              "severity": "MEDIUM",
              "root_cause": "Email validation regex does not match RFC 5322 standard",
              "detailed_explanation": "400 Bad Request on 150 out of 10,000 user profile updates. System functional but rejecting valid emails",
              "recommended_fix": "Update email validation regex to match RFC 5322, notify affected users to re-submit data",
              "prevention_strategy": "Implement proper email validation library and add integration tests",
              "confidence_score": 0.90,
              "is_recurrent_pattern": false,
              "affected_services": ["user-service"],
              "suggested_monitoring": ["email_validation_failures", "user_profile_update_rate"]
            }
            ```

            ### Example 6: LOW - Rate Limit Exceeded
            ```json
            {
              "log_id": "aa0e8400-e29b-41d4-a716-446655440005",
              "category": "RATE_LIMIT",
              "severity": "LOW",
              "root_cause": "API rate limit policy: 100 requests/minute per user",
              "detailed_explanation": "User triggered 101 requests in 1 minute. System working correctly, just throttling",
              "recommended_fix": "Show rate limit warning at 80% usage, suggest implementing batching for bulk operations",
              "prevention_strategy": "Add quota management system with visual indicators and soft limits",
              "confidence_score": 0.95,
              "is_recurrent_pattern": true,
              "affected_services": ["api-gateway"],
              "suggested_monitoring": ["rate_limit_exceeded_total", "rate_limit_by_user", "rate_limit_by_endpoint"]
            }
            ```

            ### Example 7: CRITICAL - Revenue Impact (Stripe Down)
            ```json
            {
              "log_id": "bb0e8400-e29b-41d4-a716-446655440006",
              "category": "PAYMENT_FAILURE",
              "severity": "CRITICAL",
              "root_cause": "Stripe API connection failed, blocking all payments",
              "detailed_explanation": "Revenue impact detected - $92,450 lost in 5 minutes from 312 failed transactions",
              "recommended_fix": "Immediately contact Stripe support, activate backup payment provider, rollback failed transactions",
              "prevention_strategy": "Implement multi-provider payment routing with automatic failover to prevent single point of failure",
              "confidence_score": 1.0,
              "is_recurrent_pattern": false,
              "affected_services": ["payment-service", "checkout-service", "billing-service"],
              "suggested_monitoring": ["payment_decline_rate", "payment_success_rate", "stripe_api_health_status", "failed_revenue"]
            }
            ```

            ## Validation Rules

            - Each analysis entry MUST contain all required fields
            - Severity must be one of: CRITICAL, HIGH, MEDIUM, LOW
            - **Severity must match impact level:**
              * CRITICAL: System down, 100% users affected, data loss
              * HIGH: Critical functionality broken, 50-100% users affected, revenue impact
              * MEDIUM: Non-critical errors, 10-50% users affected, system still works
              * LOW: Performance issues, <10% users affected, system operational
            - Confidence score must be 0.0-1.0 (1 decimal place)
            - Categories must be one of: API_ERROR, PAYMENT_FAILURE, TIMEOUT, RATE_LIMIT, DEPENDENCY_DOWN
            - All string fields should be concise (max character limits)
            - Confidence score < 0.7 must be accompanied by "uncertain" in explanation

            Now, analyze the input log entries and provide the strict JSON output as required.
        """)

    def analyze_logs_task(self, agent, logs_content):
        """General log analysis task using the optimized prompt template"""
        prompt_template = self.create_prompt_template()
        # Use string replacement instead of format() to avoid conflicts with curly braces in JSON
        description = prompt_template.replace("{log_entries}", logs_content)
        return Task(
            description=description,
            agent=agent,
            expected_output="Structured JSON analysis with severity levels and actionable recommendations.",
            output_pydantic=None  # Will validate output later
        )

    def validate_output_task(self, agent, analysis_json):
        """Task to validate LLM output against strict schema"""
        return Task(
            description=dedent(f"""\
                Validate the following JSON analysis against the strict schema requirements.
                
                SCHEMA REQUIREMENTS:
                - All required fields must be present
                - Severity must be one of: CRITICAL, HIGH, MEDIUM, LOW
                - Confidence score must be 0.0-1.0
                - Categories must be: API_ERROR, PAYMENT_FAILURE, TIMEOUT, RATE_LIMIT, DEPENDENCY_DOWN
                - Low confidence (<0.7) must include "uncertain" in explanation
                
                INPUT JSON:
                {analysis_json}
                
                VALIDATION CHECKLIST:
                1. Is JSON valid?
                2. Are all required fields present?
                3. Are types correct?
                4. Are values within expected ranges?
                5. Are there any quality issues?
                
                Return a JSON object with:
                - "is_valid": boolean
                - "warnings": list of strings
                - "errors": list of strings
                - "validated_json": the cleaned JSON if valid
            """),
            agent=agent,
            expected_output="Validation report with pass/fail status and any issues found."
        )

    def generate_report_task(self, agent, validated_analysis):
        """Task to compile final reports from validated analysis"""
        return Task(
            description=dedent(f"""\
                Compile a comprehensive operational intelligence report from the validated analysis.
                
                INPUT:
                {validated_analysis}
                
                REPORT STRUCTURE:
                # Operational Intelligence Report
                
                ## Executive Summary
                - Total errors analyzed
                - Most critical issues
                - Key recommendations
                
                ## Detailed Analysis
                For each log entry:
                - Error Category & Severity
                - Root Cause
                - Detailed Explanation
                - Recommended Fix
                - Prevention Strategy
                
                ## Risk Assessment
                - Recurrence probability
                - Business impact
                - System stability
                
                ## Monitoring Recommendations
                Suggested metrics to track
                
                Format as Markdown.
            """),
            agent=agent,
            expected_output="A comprehensive markdown report with actionable insights."
        )
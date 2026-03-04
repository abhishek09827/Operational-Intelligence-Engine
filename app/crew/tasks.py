from crewai import Task
from textwrap import dedent

class OpsTasks:
    def create_prompt_template(self):
        """Create the optimized prompt template for operational intelligence"""
        return dedent("""
            You are a senior Site Reliability Engineer (SRE) and distributed systems expert.

            You are analyzing multi-line production logs from a microservices architecture running in Kubernetes.

            Your task is to generate a structured operational incident report that demonstrates system-level reasoning — not just summarization.

            Strict Requirements:

            Do NOT repeat log text verbatim.

            Do NOT use generic categories like "API_ERROR".

            NEVER assign confidence = 1.0.

            You must:

            Identify primary root cause

            Identify cascading impacts across services

            Classify category and subcategory precisely

            Justify severity level

            Provide realistic remediation steps

            Suggest meaningful monitoring metrics

            Assign probabilistic confidence (0.70–0.95 range)

            Distinguish between:

            Primary cause

            Secondary symptoms

            User-facing impact

            If the incident includes infra-level failure (OOM, timeout, lock contention, circuit breaker), explicitly mention orchestration or system behavior.

            ## Task
            Analyze the following log entries and provide structured operational intelligence.

            ## Input Log Entries
            {log_entries}

            ## Output Schema (Strict JSON Format - NO MARKDOWN)

            {
              "analysis": [
                {
                  "log_id": "uuid",
                  "category": "API_ERROR | PAYMENT_FAILURE | TIMEOUT | RATE_LIMIT | DEPENDENCY_DOWN | NETWORK_ISSUE | DATABASE_ISSUE | CACHE_ISSUE | LOCK_CONTENTION | CIRCUIT_BREAKER | OOM | OTHER",
                  "subcategory": "string (e.g., 'Connection Pool Exhaustion', 'Stripe Integration Failure', 'Service Dependency Timeout')",
                  "severity": "CRITICAL | HIGH | MEDIUM | LOW",
                  "root_cause": "string (max 200 chars) - Identify primary root cause",
                  "primary_cause": "string (max 150 chars) - What failed first",
                  "secondary_symptoms": ["array of strings (max 3) - Cascading effects"],
                  "user_impact": "string (max 200 chars) - User-facing consequences",
                  "orchestration_behavior": "string (optional) - If infra-level failure, describe system behavior (circuit breaker, retries, etc.)",
                  "detailed_explanation": "string (max 500 chars) - System-level reasoning",
                  "recommended_fix": "string (max 300 chars) - Immediate remediation steps",
                  "prevention_strategy": "string (max 300 chars) - Long-term architectural improvements",
                  "confidence_score": 0.70-0.95,
                  "is_recurrent_pattern": boolean,
                  "affected_services": ["array of strings"],
                  "suggested_monitoring": ["array of metrics"]
                }
              ],
              "summary": {
                "total_errors": integer,
                "high_severity_count": integer,
                "most_common_category": string,
                "most_common_subcategory": string,
                "primary_root_cause": "string",
                "recommendations": ["array of general recommendations"]
              }
            }

            ## CRITICAL OUTPUT REQUIREMENTS
            1. **OUTPUT MUST BE ONLY JSON** - No markdown, no bullet points, no emojis, no headers
            2. **NO CODE BLOCKS** - Do NOT use ```json or any other code block markers
            3. **NO EXPLANATIONS** - Output ONLY the JSON object, nothing else
            4. **NO NEWLINE AFTER JSON** - Do NOT add a newline character after the JSON
            5. **ONE ENTRY PER LOG** - Do NOT combine multiple logs into one analysis

            ## Severity Classification Guide (CRITICAL, HIGH, MEDIUM, LOW)

            **CRITICAL (System Unavailable or Major Data Loss)**
            - User-facing outage blocking core functionality
            - System crash or restart (OOMKilled, fatal error)
            - All services affected or complete checkout/payment flow blocked
            - Data loss or corruption
            - Circuit breaker OPEN preventing all requests
            - Database unavailable or all connections exhausted
            - Any error affecting 100% of users
            - Security breach or vulnerability in production

            **HIGH (Major Degradation but Partial Functionality)**
            - Single critical service degraded (e.g., payment service down)
            - 503 errors preventing requests from specific endpoints
            - Database pool exhaustion (16+ requests waiting)
            - Payment decline rate > 10% with revenue impact
            - Single endpoint timing out with 3+ retry attempts
            - Specific critical functionality partially broken
            - Downstream dependency failures cascading to user impact
            - Circuit breaker OPEN affecting specific service but system operational

            **MEDIUM (Localized or Recoverable Issue)**
            - Non-critical endpoint errors (4xx)
            - Rate limiting throttling but system still functional
            - Performance degradation (slower but works)
            - Errors affecting 10-50% of requests
            - Non-critical service timeouts
            - Minor validation errors
            - Cache issues affecting specific data

            **LOW (Validation or Non-Production Issue)**
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
            5. **Confidence Score**: Must be in range 0.70-0.95
               - 0.90+ only if logs show explicit fatal indicators (e.g., OOMKilled, fatal error, all connections exhausted)
               - 0.75-0.89 if strong inference but indirect evidence
               - <0.75 if ambiguous signals
            6. **Prevention**: Focus on long-term improvements, not just fixes
            7. **Tone**: Professional, deterministic, operational, no hype, no emojis, no vague statements

            ## Validation Rules

            - Each analysis entry MUST contain all required fields
            - Severity must be one of: CRITICAL, HIGH, MEDIUM, LOW
            - **Severity must match impact level:**
              * CRITICAL: System down, 100% users affected, data loss
              * HIGH: Critical functionality broken, 50-100% users affected, revenue impact
              * MEDIUM: Non-critical errors, 10-50% users affected, system still works
              * LOW: Performance issues, <10% users affected, system operational
            - Confidence score must be in range 0.70-0.95 (1 decimal place)
            - Categories must be one of: API_ERROR, PAYMENT_FAILURE, TIMEOUT, RATE_LIMIT, DEPENDENCY_DOWN, NETWORK_ISSUE, DATABASE_ISSUE, CACHE_ISSUE, LOCK_CONTENTION, CIRCUIT_BREAKER, OOM, OTHER
            - Subcategory must be specific and descriptive
            - Primary cause must identify what failed first
            - Secondary symptoms must describe cascading effects (max 3)
            - User impact must describe user-facing consequences
            - All string fields should be concise (max character limits)
            - NEVER assign confidence = 1.0

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

    def validate_output_task(self, agent):
        """Task to validate LLM output against strict schema"""
        return Task(
            description=dedent(f"""\
                Validate the output from the previous task (JSON analysis) against the strict schema requirements.
                
                SCHEMA REQUIREMENTS:
                - All required fields must be present (log_id, category, severity, root_cause, detailed_explanation, recommended_fix, prevention_strategy, confidence_score, is_recurrent_pattern, affected_services, suggested_monitoring)
                - Severity must be one of: CRITICAL, HIGH, MEDIUM, LOW
                - Category must be one of: API_ERROR, PAYMENT_FAILURE, TIMEOUT, RATE_LIMIT, DEPENDENCY_DOWN, NETWORK_ISSUE, DATABASE_ISSUE, CACHE_ISSUE, LOCK_CONTENTION, CIRCUIT_BREAKER, OOM, OTHER
                - Subcategory must be present and specific
                - Confidence score must be in range 0.70-0.95
                - Primary cause must be present
                - Secondary symptoms must be an array (max 3 items)
                - User impact must be present
                - Secondary symptoms max 3 items
                - orchestration_behavior is optional
                
                CONFIDENCE SCORE VALIDATION:
                - CRITICAL: 0.90-0.95 (only if explicit fatal indicators like OOMKilled, fatal error, all connections exhausted)
                - HIGH: 0.85-0.95 (strong inference but indirect evidence)
                - MEDIUM: 0.75-0.89
                - LOW: 0.70-0.79
                - NEVER allow 1.0
                
                INPUT: The previous task's output (JSON analysis) is automatically available.
                
                VALIDATION CHECKLIST:
                1. Is JSON valid syntax?
                2. Are all required fields present?
                3. Are string fields concise (within character limits)?
                4. Are types correct?
                5. Are confidence scores in valid range (0.70-0.95)?
                6. Is confidence never 1.0?
                7. Are secondary symptoms limited to max 3 items?
                8. Is subcategory specific and descriptive?
                9. Is primary cause clearly identified?
                10. Are user impact and orchestration_behavior described appropriately?
                
                IMPORTANT: Simply validate the JSON and return it unchanged if it meets all requirements.
                DO NOT modify the JSON structure - just verify it's correct.
                DO NOT create validation reports or warnings - just pass through the JSON.
            """),
            agent=agent,
            expected_output="The same JSON analysis if valid."
        )

    def generate_report_task(self, agent):
        """Task to compile final reports from validated analysis"""
        return Task(
            description=dedent(f"""\
                Compile a comprehensive operational intelligence report from the validated analysis.
                
                INPUT: The previous task's output (JSON analysis) is automatically available.
                
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
from crewai import Task
from textwrap import dedent

class OpsTasks:
    def analyze_logs_task(self, agent, logs_content):
        return Task(
            description=dedent(f"""\
                Analyze the following system logs for errors, exceptions, and anomalies.
                Identify the timestamp, service, and error message of the critical failure.
                
                LOGS:
                {logs_content}
            """),
            agent=agent,
            expected_output="A structured summary of the error found in the logs."
        )

    def identify_root_cause_task(self, agent, context):
        return Task(
            description=dedent(f"""\
                Based on the log analysis provided, determine the root cause of the incident.
                Consider potential configuration issues, code bugs, or resource constraints.
                Explain the 'Why'.
            """),
            agent=agent,
            context=context,
            expected_output="A detailed explanation of the root cause."
        )

    def suggest_fix_task(self, agent, context):
        return Task(
            description=dedent(f"""\
                Based on the identified root cause, suggest a concrete technical fix.
                Provide code snippets, config changes, or commands if applicable.
                Explain why this fix solves the root problem.
            """),
            agent=agent,
            context=context,
            expected_output="Actionable steps to resolve the incident."
        )

    def generate_report_task(self, agent, context):
        return Task(
            description=dedent(f"""\
                Compile a final incident report including:
                1. Executive Summary
                2. Technical Detail of the Error
                3. Root Cause Analysis
                4. Recommended Fixes
                
                Format as Markdown.
            """),
            agent=agent,
            context=context,
            expected_output="A full markdown incident report."
        )

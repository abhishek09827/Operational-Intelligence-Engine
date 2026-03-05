from crewai import Crew, Process
from app.crew.agents import OpsAgents
from app.crew.tasks import OpsTasks

from sqlalchemy.orm import Session
from app.rag.vector_db import VectorDBService

class OpsCrew:
    def __init__(self, incident_id: str, logs_content: str, db_session: Session):
        self.incident_id = incident_id
        self.logs_content = logs_content
        self.db_session = db_session
        self.agents = OpsAgents()
        self.tasks = OpsTasks()

    def route_to_agent(self, logs_content: str):
        """Route logs to the most appropriate agent based on error patterns"""
        log_lines = logs_content.lower()
        
        # Define routing rules based on keywords (excludes validation and report agents)
        if any(keyword in log_lines for keyword in ['payment', 'transaction', 'stripe', 'paypal', 'fraud', 'decline', 'authorization']):
            return self.agents.payment_failure_agent()
        elif any(keyword in log_lines for keyword in ['timeout', 'timeout occurred', 'timed out', 'retry attempt', 'circuit breaker']):
            return self.agents.timeout_agent()
        elif any(keyword in log_lines for keyword in ['rate limit', '429', 'too many requests', 'quota exceeded', 'throttle']):
            return self.agents.rate_limit_agent()
        elif any(keyword in log_lines for keyword in ['dependency', 'downstream', 'external service', 'down', 'unavailable']):
            return self.agents.dependency_agent()
        else:
            # Default to API error agent for general errors
            return self.agents.api_error_agent()

    def run(self):
        # Retrieve historical context
        vector_service = VectorDBService(self.db_session)
        similar_incidents = vector_service.search_similar_incidents(self.logs_content)
        
        history_context = ""
        if similar_incidents:
            history_context = "\n\nRELATED HISTORICAL INCIDENTS:\n"
            for inc in similar_incidents:
                history_context += f"- Date: {inc.created_at}, Title: {inc.title}, Root Cause: {inc.root_cause}\n"

        # Route to the appropriate agent based on log patterns for initial analysis
        selected_agent = self.route_to_agent(self.logs_content)
        analysis_agent = selected_agent

        # Create analysis task
        logs_with_history = f"{self.logs_content}\n{history_context}\n\nAgent: {analysis_agent.role}"
        analysis_task = self.tasks.analyze_logs_task(analysis_agent, logs_with_history)

        # Create validation task to ensure output quality
        validation_task = self.tasks.validate_output_task(analysis_agent)

        # Create report generation task to compile final report
        report_task = self.tasks.generate_report_task(analysis_agent)

        # Form a multi-agent crew for comprehensive analysis
        crew = Crew(
            agents=[
                analysis_agent,       # Analyzes the logs
                self.agents.validation_agent(),  # Validates the output schema
                self.agents.report_generator_agent()  # Generates final report
            ],
            tasks=[analysis_task, validation_task, report_task],
            process=Process.sequential,
            verbose=True
        )

        result = crew.kickoff()
        
        # Capture all task outputs before they're cleared
        task_outputs = []
        for task in crew.tasks:
            if hasattr(task, 'output') and task.output:
                task_outputs.append(task.output)
            elif hasattr(task, 'task_output') and task.task_output:
                task_outputs.append(task.task_output)
        
        return result, task_outputs

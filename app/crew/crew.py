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

    def run(self):
        # Retrieve historical context
        vector_service = VectorDBService(self.db_session)
        similar_incidents = vector_service.search_similar_incidents(self.logs_content)
        
        history_context = ""
        if similar_incidents:
            history_context = "\n\nRELATED HISTORICAL INCIDENTS:\n"
            for inc in similar_incidents:
                history_context += f"- Date: {inc.created_at}, Title: {inc.title}, Root Cause: {inc.root_cause}\n"

        # Use the specialized log analysis agent
        log_analyst = self.agents.api_error_agent()

        # Instantiate Tasks
        # Inject history into the task
        logs_with_history = f"{self.logs_content}\n{history_context}"
        
        # Create analysis task ONLY - no report generator, no validation
        analysis_task = self.tasks.analyze_logs_task(log_analyst, logs_with_history)

        # Form the Crew
        crew = Crew(
            agents=[log_analyst],
            tasks=[analysis_task],
            process=Process.sequential,
            verbose=True
        )

        result = crew.kickoff()
        return result

from crewai import Crew, Process
from app.crew.agents import OpsAgents
from app.crew.tasks import OpsTasks

class OpsCrew:
    def __init__(self, incident_id: str, logs_content: str):
        self.incident_id = incident_id
        self.logs_content = logs_content
        self.agents = OpsAgents()
        self.tasks = OpsTasks()

    def run(self):
        # Instantiate Agents
        log_analyst = self.agents.log_analysis_agent()
        root_cause_analyst = self.agents.root_cause_agent()
        fix_suggester = self.agents.fix_suggester_agent()
        reporter = self.agents.report_generator_agent()

        # Instantiate Tasks
        analysis_task = self.tasks.analyze_logs_task(log_analyst, self.logs_content)
        root_cause_task = self.tasks.identify_root_cause_task(root_cause_analyst, [analysis_task])
        fix_task = self.tasks.suggest_fix_task(fix_suggester, [root_cause_task])
        report_task = self.tasks.generate_report_task(reporter, [analysis_task, root_cause_task, fix_task])

        # Form the Crew
        crew = Crew(
            agents=[log_analyst, root_cause_analyst, fix_suggester, reporter],
            tasks=[analysis_task, root_cause_task, fix_task, report_task],
            process=Process.sequential,
            verbose=2
        )

        result = crew.kickoff()
        return result

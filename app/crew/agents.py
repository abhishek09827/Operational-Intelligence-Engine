from crewai import Agent
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings

class OpsAgents:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL_NAME,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.7
        )

    def log_analysis_agent(self):
        return Agent(
            role='Senior Log Analyst',
            goal='Analyze system logs to identify patterns, errors, and anomalies.',
            backstory=(
                "You are an expert Log Analyst with years of experience in distributed systems. "
                "Your job is to sift through raw logs, filter out noise, and highlight critical "
                "failure points. You understand stack traces, error codes, and service dependencies."
            ),
            verbose=True,
            llm=self.llm,
            allow_delegation=False
        )

    def root_cause_agent(self):
        return Agent(
            role='Root Cause Analysis Expert',
            goal='Determine the fundamental cause of the incident based on analysis.',
            backstory=(
                "You are a systems architect and reliability engineer. Given log analysis "
                "and system context, you identify exactly why a system failed. "
                "You look beyond the immediate error to find architectural or logical flaws."
            ),
            verbose=True,
            llm=self.llm,
            allow_delegation=False
        )

    def fix_suggester_agent(self):
        return Agent(
            role='Site Reliability Engineer (FixSuggester)',
            goal='Propose actionable technical fixes for the identified root cause.',
            backstory=(
                "You are a pragmatic SRE. Your goal is to get the system back up and running "
                "and prevent recurrence. You suggest code changes, configuration updates, "
                "or infrastructure scaling operations. You provide specific, executable commands or code."
            ),
            verbose=True,
            llm=self.llm,
            allow_delegation=False
        )

    def report_generator_agent(self):
        return Agent(
            role='Incident Commander / Technical Writer',
            goal='Compile a comprehensive incident report.',
            backstory=(
                "You are responsible for communicating the incident state. "
                "You gather all insights from the analysis, root cause, and fix steps "
                "to produce a structured, markdown-formatted incident report for the team."
            ),
            verbose=True,
            llm=self.llm,
            allow_delegation=False
        )

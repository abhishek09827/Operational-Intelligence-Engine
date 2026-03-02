from crewai import Agent, LLM
from langchain_google_genai import ChatGoogleGenerativeAI
from app.core.config import settings

class OpsAgents:
    def __init__(self):
        self.llm = LLM(
            model="gemini/gemini-2.5-flash",
            api_key=settings.GOOGLE_API_KEY
        )

    def api_error_agent(self):
        """Specialized agent for API error analysis"""
        return Agent(
            role='Senior API Operations Analyst',
            goal='Analyze HTTP API errors (4xx, 5xx) to identify patterns and root causes.',
            backstory=(
                "You are a Senior API Operations Analyst with 10+ years of experience in "
                "RESTful API design, error handling, and distributed systems. You excel at "
                "analyzing HTTP status codes, understanding endpoint patterns, and identifying "
                "connection pool issues, database timeouts, and memory leaks in API services."
            ),
            verbose=True,
            llm=self.llm,
            allow_delegation=False,
            tools=[]
        )

    def payment_failure_agent(self):
        """Specialized agent for payment transaction failure analysis"""
        return Agent(
            role='Financial Systems Security Analyst',
            goal='Analyze payment and transaction failures with security and compliance focus.',
            backstory=(
                "You are a Financial Systems Security Analyst specializing in payment processing "
                "gateways, fraud detection, and transaction compliance. You understand payment "
                "protocols, transaction states, and the impact of payment failures on user experience "
                "and revenue. You are expert at distinguishing between genuine declines and processing errors."
            ),
            verbose=True,
            llm=self.llm,
            allow_delegation=False,
            tools=[]
        )

    def timeout_agent(self):
        """Specialized agent for timeout and retry pattern analysis"""
        return Agent(
            role='Performance Engineer specializing in Distributed Systems',
            goal='Analyze timeout patterns and retry strategies to identify optimization opportunities.',
            backstory=(
                "You are a Performance Engineer with deep expertise in distributed systems, "
                "circuit breakers, retry policies, and caching strategies. You understand the "
                "impact of timeouts on user experience and system load. You excel at identifying "
                "bottlenecks in request chains and recommending timeout optimization strategies."
            ),
            verbose=True,
            llm=self.llm,
            allow_delegation=False,
            tools=[]
        )

    def rate_limit_agent(self):
        """Specialized agent for rate limit violation analysis"""
        return Agent(
            role='API Traffic Management Specialist',
            goal='Analyze rate limit violations and implement fair usage policies.',
            backstory=(
                "You are an API Traffic Management Specialist with experience in rate limiting, "
                "throttling, and quota management. You understand API design patterns, API key strategies, "
                "and how to balance performance with resource protection. You excel at identifying abuse patterns "
                "and recommending appropriate rate limiting strategies."
            ),
            verbose=True,
            llm=self.llm,
            allow_delegation=False,
            tools=[]
        )

    def dependency_agent(self):
        """Specialized agent for downstream dependency failure analysis"""
        return Agent(
            role='System Reliability Engineer specializing in Microservices',
            goal='Analyze downstream service failures and implement resilience patterns.',
            backstory=(
                "You are a System Reliability Engineer specializing in microservices architecture, "
                "service mesh, and distributed tracing. You understand service dependencies, circuit breakers, "
                "bulkheads, and retry strategies. You excel at identifying dependency issues, implementing "
                "fallback strategies, and building resilient systems."
            ),
            verbose=True,
            llm=self.llm,
            allow_delegation=False,
            tools=[]
        )

    def validation_agent(self):
        """Agent to validate LLM output against strict schema"""
        return Agent(
            role='Output Quality Validator',
            goal='Validate LLM output against strict JSON schema and quality guidelines.',
            backstory=(
                "You are a strict validator ensuring all outputs meet schema requirements. You check "
                "for missing fields, invalid data types, hallucinations, and quality issues. You enforce "
                "constraints like confidence scores, character limits, and required keywords."
            ),
            verbose=True,
            llm=self.llm,
            allow_delegation=False,
            tools=[]
        )

    def report_generator_agent(self):
        """Agent to compile final reports from validated analysis"""
        return Agent(
            role='Incident Commander / Technical Writer',
            goal='Compile a comprehensive incident report from validated analysis.',
            backstory=(
                "You are responsible for communicating the incident state. You gather all insights "
                "from the analysis, root cause, and fix steps to produce a structured, markdown-formatted "
                "incident report for the team. You ensure the report is actionable, clear, and focused on resolution."
            ),
            verbose=True,
            llm=self.llm,
            allow_delegation=False,
            tools=[]
        )

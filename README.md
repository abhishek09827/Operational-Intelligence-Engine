# OpsPilot.ai 🚀

**OpsPilot.ai** is an advanced, agentic AI assistant designed to streamline Incident Response and SRE workflows. Leveraging the power of CrewAI, RAG (Retrieval-Augmented Generation), and modern LLMs (Google Gemini), OpsPilot automates log analysis, root cause identification, and remediation planning.

## 🌟 Features

- **Automated Incident Analysis**: Intelligently parses and analyzes logs to detect anomalies.
- **Root Cause Analysis (RCA)**: Uses multi-agent collaboration to pinpoint the exact source of failures.
- **Smart Remediation**: Suggests actionable fixes based on historical data and best practices.
- **Comprehensive Reporting**: Generates detailed incident reports for post-mortem analysis.
- **RAG Integration**: search through historical incident data using vector embeddings (pgvector).
- **Observability**: Built-in Prometheus instrumentation for real-time monitoring.

## Architecture
- **CrewAI**: Orchestrates agents.
- **FastAPI**: Backend API.
- **Docker**: Containerization.
- **PostgreSQL**: Database.

## Setup
1. Clone the repo.
2. Run `docker-compose up --build`.

## Usage
Access the API at `http://localhost:8000`.

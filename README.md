# OpsPilot.ai 🚀

**OpsPilot.ai** is an advanced, agentic AI assistant designed to streamline Incident Response and SRE workflows. Leveraging the power of CrewAI, RAG (Retrieval-Augmented Generation), and modern LLMs (Google Gemini), OpsPilot automates log analysis, root cause identification, and remediation planning.

## 🌟 Features

- **Automated Incident Analysis**: Intelligently parses and analyzes logs to detect anomalies.
- **Root Cause Analysis (RCA)**: Uses multi-agent collaboration to pinpoint the exact source of failures.
- **Smart Remediation**: Suggests actionable fixes based on historical data and best practices.
- **Comprehensive Reporting**: Generates detailed incident reports for post-mortem analysis.
- **RAG Integration**: search through historical incident data using vector embeddings (pgvector).
- **Observability**: Built-in Prometheus instrumentation for real-time monitoring.

## 🏗️ Architecture

The system follows a microservices-based architecture powered by Docker containers.

<img width="2631" height="838" alt="Untitled-2026-02-07-1602" src="https://github.com/user-attachments/assets/50e71414-8488-4413-b37f-8216166e4f62" />



> **Note**: This diagram handles high-level data flow. You can copy the Mermaid code above and paste it into [Excalidraw](https://excalidraw.com/) (using the "Mermaid" tool) for further editing.

## 🛠️ Tech Stack

- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **AI/Agents**: [CrewAI](https://crewai.com/), [LangChain](https://langchain.com/)
- **LLM**: Google Gemini
- **Database**: PostgreSQL (with `pgvector` extension)
- **Caching/Queue**: Redis
- **Monitoring**: Prometheus
- **Containerization**: Docker & Docker Compose

## 🚀 Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.10+ (for local development)
- Google AI Studio API Key

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/OpsPilot.ai.git
   cd OpsPilot.ai
   ```

2. **Configure Environment**:
   Create a `.env` file in the root directory:
   ```env
   GOOGLE_API_KEY=your_google_api_key_here
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=postgres
   POSTGRES_DB=opspilot
   DATABASE_URL=postgresql://postgres:postgres@db:5432/opspilot
   ```

3. **Run with Docker**:
   ```bash
   docker-compose up --build -d
   ```

4. **Access the API**:
   - Swagger UI: `http://localhost:8000/docs`
   - Health Check: `http://localhost:8000/health`

## 🧪 Testing

Run typical tests using pytest:

```bash
docker-compose run app pytest
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request


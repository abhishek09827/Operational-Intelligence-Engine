<div align="center">
  <h1>Operational Intelligence Engine 🚀</h1>
  <p><b>An advanced, agentic AI assistant designed to streamline Incident Response and SRE workflows.</b></p>
</div>

Leveraging the power of CrewAI, RAG (Retrieval-Augmented Generation), and modern LLMs (Google Gemini), the **Operational Intelligence Engine** automates log analysis, root cause identification, and remediation planning, acting as a force multiplier for your operations team.

---

## 🌟 Key Features

- **Automated Incident Analysis**: Intelligently parses and analyzes messy, unstructured logs to detect anomalies and extract structured data.
- **Agentic Root Cause Analysis (RCA)**: Uses multi-agent collaboration via CrewAI to pinpoint the exact source of failures.
- **Smart Remediation**: Suggests actionable, step-by-step fixes based on historical incident data and SRE best practices.
- **RAG-Powered Intelligence**: Semantic search across historical incident records using vector embeddings (`pgvector`) to find similar past issues.
- **Comprehensive Reporting**: Automatically generates detailed incident reports and post-mortems for stakeholders.
- **Built-in Observability**: Includes Prometheus instrumentation for real-time API monitoring.

## 🏗️ Architecture

The system follows a microservices-based architecture powered by Docker containers, separating the API layer, the intelligent agentic workflow, and the data storage layer.

<img width="2631" height="838" alt="Operational Intelligence Engine Architecture" src="https://github.com/user-attachments/assets/50e71414-8488-4413-b37f-8216166e4f62" />

## 🛠️ Tech Stack

### Core Technologies
- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python)
- **AI Orchestration**: [CrewAI](https://crewai.com/), [LangChain](https://langchain.com/)
- **Large Language Model**: Google Gemini (Pro/Flash)

### Infrastructure & Data
- **Database**: PostgreSQL (extended with `pgvector` for AI embeddings)
- **Caching & Task Queue**: Redis
- **Containerization**: Docker & Docker Compose
- **Monitoring**: Prometheus

## 🚀 Getting Started

### Prerequisites

- [Docker & Docker Compose](https://docs.docker.com/get-docker/) installed
- Python 3.10+ (if developing locally without Docker)
- A valid [Google Gemini API Key](https://aistudio.google.com/app/apikey)

### Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/abhishek09827/Operational-Intelligence-Engine.git
   cd Operational-Intelligence-Engine
   ```

2. **Configure Environment Variables**:
   Create a `.env` file in the root directory based on the provided template:
   ```env
   GOOGLE_API_KEY=your_google_api_key_here
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=postgres
   POSTGRES_DB=operational_intelligence_engine
   DATABASE_URL=postgresql://postgres:postgres@db:5432/operational_intelligence_engine
   ```

3. **Spin up the Infrastructure via Docker**:
   ```bash
   docker-compose up --build -d
   ```

4. **Access the Services**:
   - **Interactive API Docs (Swagger)**: `http://localhost:8000/docs`
   - **Health Check**: `http://localhost:8000/health`

## 🧪 Testing

We use `pytest` for unit and integration testing. To run the test suite within the Docker environment:

```bash
docker-compose run app pytest
```

## 📸 Screenshots & Output Examples

Here is a glimpse of the Operational Intelligence Engine in action:

| Architecture | Agent Execution | Example Output |
| :---: | :---: | :---: |
| ![1](https://github.com/user-attachments/assets/ae895f9a-3ca7-491d-a364-420ddd8eaefe) | ![2](<img width="2560" height="1440" alt="image" src="https://github.com/user-attachments/assets/f41d7852-e6e6-4988-94e1-9e11052828ca" />) | ![3](https://github.com/user-attachments/assets/d0d232b4-2f9b-4652-99a8-fbdb4ca12d9c) |
| ![4](https://github.com/user-attachments/assets/c7a30b0f-589d-4aab-b093-27349eb28a65) | ![5](https://github.com/user-attachments/assets/2a6b342a-c6c4-4108-9ea3-7386c347a4a1) | ![6](https://github.com/user-attachments/assets/8c1570e8-31a5-4484-a128-40e64a0e2e8f) |

Here is a glimpse of the Updated UI:

| Architecture | Agent Execution | Example Output |
| :---: | :---: | :---: |
| ![1](<img width="2560" height="1440" alt="image" src="https://github.com/user-attachments/assets/195ade99-be94-43e2-9f49-fa4d03535f69" />) | ![2](https://github.com/user-attachments/assets/ba317990-b230-44cb-9e42-2b8ae4581753) | ![3](<img width="2560" height="1440" alt="image" src="https://github.com/user-attachments/assets/c1e5eefc-bce7-492b-85af-54d42ffa69db" />) |
| ![4](<img width="2560" height="1440" alt="image" src="https://github.com/user-attachments/assets/7ec46535-c400-46d6-ba90-1e183afb31db" />) | ![5](https://github.com/user-attachments/assets/2a6b342a-c6c4-4108-9ea3-7386c347a4a1) | ![6](https://github.com/user-attachments/assets/8c1570e8-31a5-4484-a128-40e64a0e2e8f) |

## 🤝 Contributing

We welcome contributions from the community! If you'd like to improve the Operational Intelligence Engine, please follow these steps:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---
<p align="center">Built with ❤️ for Site Reliability Engineers.</p>

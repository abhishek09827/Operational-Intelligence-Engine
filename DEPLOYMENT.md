# OpsPilot Deployment Guide

## Prerequisites
- Docker Engine & Docker Compose
- PostgreSQL 16 (with pgvector extension)
- Redis 7
- Google Gemini API Key

## Local Deployment (Docker Compose)
1. **Clone Repository**:
   ```bash
   git clone https://github.com/your-repo/opspilot.git
   cd opspilot
   ```

2. **Environment Setup**:
   Copy `.env.example` to `.env` and fill in the details:
   ```bash
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=postgres
   POSTGRES_DB=opspilot
   GOOGLE_API_KEY=your_key_here
   ```

3. **Start Services**:
   ```bash
   docker-compose up -d --build
   ```
   
4. **Verify Installation**:
   Visit `http://localhost:8000/docs` to see the API Swagger UI.

## Production Deployment (Kubernetes/Nomad)
1. **Build Image**:
   The CI/CD pipeline automatically builds and pushes the image to `ghcr.io/your-username/opspilot:latest`.

2. **Infrastructure**:
   Ensure you have a PostgreSQL database with `pgvector` enabled and a Redis instance reachable from the cluster.

3. **Deploy**:
   Use standard K8s manifests or Helm charts. Ensure secrets (API keys, DB credentials) are managed via Kubernetes Secrets or Vault.

## Monitoring
- **Metrics**: Exposed at `/metrics`. Scrape with Prometheus.
- **Logs**: JSON formatted logs to stdout. Collect with Fluentd/Filebeat.

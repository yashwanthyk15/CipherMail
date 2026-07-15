# CipherMail

An enterprise-grade Email Security Gateway that intercepts and analyzes emails in real-time to detect phishing, malware, and spam using AI and threat intelligence.

## Features

* **Dual Ingestion**: 
  * **SMTP Gateway**: Receives emails directly via standard SMTP protocol.
  * **Gmail Connector**: Seamlessly connects to your personal or corporate Gmail inbox to scan and label emails automatically (`ESG-Safe`, `ESG-Phishing`, `ESG-Quarantine`, `ESG-Blocked`).
* **Real-time Pipeline**: Built on Apache Kafka for high-throughput, asynchronous message processing.
* **AI Threat Detection**: Integrates with Google's Gemini 2.0 Flash model to intelligently analyze email body, headers, and context for phishing patterns.
* **Reputation Engine**: Uses VirusTotal and other reputation services to analyze URLs and attachments.
* **Microservices Architecture**: Fully containerized using Docker for easy deployment and scaling.
* **React Dashboard**: A premium, real-time dashboard built with React, TailwindCSS, and WebSocket for monitoring threats.

## Architecture

1. **Ingestion Layer**: `smtp-gateway` or `gmail-connector` receives emails.
2. **Event Bus**: Emails are published to `kafka` (`email.events` topic).
3. **Analysis Workers**:
   * `ai-worker`: Uses LLM (Gemini) to score phishing risk based on text semantics.
   * `reputation-worker`: Scans attachments and links against threat databases.
4. **Decision Engine**: Combines analysis results into a final security decision (ALLOW, QUARANTINE, BLOCK).
5. **Storage**: `postgres` stores historical data and decisions, `redis` handles caching and temporary mapping.
6. **API & UI**: FastAPI backend provides data to a React-based security operations dashboard.

## Tech Stack

* **Backend**: Python, FastAPI, asyncio
* **Frontend**: React 18, TypeScript, TailwindCSS, Vite
* **Infrastructure**: Docker, Docker Compose, Kafka, Zookeeper, PostgreSQL, Redis
* **AI/Security**: Google Gemini API, VirusTotal API

## Getting Started (Local Development)

### Prerequisites

* Docker and Docker Compose
* Python 3.11+ (for local scripts)
* API Keys for Gemini and VirusTotal

### Setup

1. **Clone the repository**
2. **Environment Variables**: Copy `.env.example` to `.env` and fill in your API keys.
3. **Gmail Auth (Optional)**: If using the Gmail connector, run `python scripts/setup_gmail_auth.py` to generate your OAuth token.
4. **Run the stack**:
   ```bash
   docker-compose up --build -d
   ```
5. **Access the Dashboard**: Open `http://localhost:3002` in your browser.

## Services

* `gmail-connector`: Polls Gmail, sends to Kafka, applies labels based on decisions.
* `smtp-gateway`: Listens on port 587 for incoming SMTP traffic.
* `ai-worker`: Consumes from Kafka, queries Gemini API, publishes risk scores.
* `reputation-worker`: Consumes from Kafka, checks URLs/attachments, publishes risk scores.
* `api`: FastAPI backend serving dashboard data and handling webhooks.
* `dashboard`: React frontend UI.
* `attack-simulator`: Generates mock phishing traffic for testing.

## Infrastructure Map

* Dashboard: `http://localhost:3002`
* API: `http://localhost:8000`
* Postgres: `localhost:5432`
* Redis: `localhost:6379`
* Kafka: `localhost:9092`

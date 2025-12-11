# 🧠 Multi-Agent AI System: The Complete Guide

> **Enterprise-grade autonomous agent framework built for reliability, observability, and safety.**

This repository hosts a production-ready framework for building, deploying, and managing autonomous AI agents. It goes beyond simple "prompts" by implementing sophisticated infrastructure for **safety**, **cost control**, and **version management**.

---

## 📚 Table of Contents

1.  [System Architecture](#-system-architecture)
2.  [The Agent Graph](#-the-agent-graph)
3.  [Core Infrastructure Features](#-core-infrastructure-features)
    -   [Reliability & Recovery](#reliability--recovery)
    -   [Workflow Versioning & Shadow Mode](#workflow-versioning--shadow-mode)
    -   [Cost Tracking](#cost-tracking)
4.  [Setup & Installation](#-setup--installation)
5.  [Configuration Reference](#-configuration-reference)
6.  [Developer Guide](#-developer-guide)
    -   [Codebase Structure](#codebase-structure)
    -   [How to Add a New Tool](#how-to-add-a-new-tool)
    -   [Running Verifications](#running-verifications)

---

## 🏗️ System Architecture

The system uses a **Distributed Async Worker Pattern** to handle long-running AI tasks without blocking the API.

### High-Level Data Flow

1.  **Request Ingestion**: Client sends a request (`POST /runs`) to the **FastAPI Backend**.
2.  **Persistence**: The API creates a `WorkflowRun` record in the **Postgres/SQLite DB**.
3.  **Queueing**: The API pushes a task to **RabbitMQ** (via `aio_pika`).
4.  **Execution**: The **Worker Service** picks up the task.
5.  **Agent Loop**: The worker initializes the **LangGraph** workflow.
    -   The workflow executes multiple steps (Research -> Plan -> Code).
    -   State is checkpointed to DB after every step.
6.  **Completion**: Final result is saved to DB, and status is updated to `COMPLETED`.

```mermaid
sequenceDiagram
    participant User
    participant API
    participant DB
    participant Queue
    participant Worker
    participant LLM

    User->>API: POST /runs (query="Build a snake game")
    API->>DB: Create Run (status=QUEUED)
    API->>Queue: Push Task
    API-->>User: Return RunID

    Queue->>Worker: Consume Task
    Worker->>DB: Update Run (status=RUNNING)
    loop Agent Graph
        Worker->>LLM: Generate Plan/Code
        LLM-->>Worker: Response
        Worker->>DB: Checkpoint State
    end
    Worker->>DB: Save Result & Update (status=COMPLETED)
```

---

## 🤖 The Agent Graph

We use a specific topology of specialized agents to ensure high-quality outputs.

**Topology:** `Researcher` → `Planner` → `Executor` → `Coder` → `Finalizer`

1.  **Researcher**: Uses DuckDuckGo to gather context if the query requires external knowledge.
2.  **Planner**: Analyzes the request and research data to create a step-by-step execution plan.
3.  **Executor**: Validates the plan and prepares technical architecture notes.
4.  **Coder**: Generates the actual artifacts (Python code, React components, etc.).
5.  **Finalizer**: Synthesizes everything into a user-friendly response.

*Logic Source:* `backend/app/agents/graph.py`

---

## 🛡️ Core Infrastructure Features

This is what sets this project apart from a toy demo.

### Reliability & Recovery
*(Docs: `docs/ERROR_HANDLING.md`)*
-   **Problem**: LLMs fail. APIs timeout. Agents hallucinogenic loops.
-   **Solution**:
    -   **Circuit Breakers**: If the Groq API fails 5 times in a row, the `CircuitBreaker` opens to prevent system overload.
    -   **Exponential Backoff**: Retries failed calls with jitter (randomized delay).
    -   **State Checkpointing**: If the worker crashes, the workflow acts as a "durable execution" and resumes from the last saved checkpoint.

### Workflow Versioning & Shadow Mode
*(Docs: `docs/WORKFLOW_VERSIONING.md`)*
-   **Problem**: Updating an agent prompt might break edge cases.
-   **Solution**:
    -   **Snapshots**: Every deployment zips up code + prompts (`storage/snapshots/`).
    -   **Shadow Mode**: Deploy a "Candidate" version (v2) alongside "Active" (v1). V2 runs silently on 5% of traffic.
    -   **Divergence Detection**: The system compares V1 output vs V2 output. If V2 diverges significantly (score < 0.85), an alert is logged.
    -   **Rollback**: API allows instant rollback to previous snapshot ID.

### Cost Tracking
*(Docs: `docs/COST_TRACKING.md`)*
-   **Problem**: Infinite agent loops drain the credit card.
-   **Solution**:
    -   **Token Counting**: Intercepts every LLM call to count prompt/completion tokens.
    -   **Attribution**: Costs are tagged by `WorkflowID` and `AgentID`.
    -   **Budgeting**: (Planned) Auto-kill workflows exceeding $X.

---

## ⚙️ Setup & Installation

### Prerequisites
-   **Docker Desktop** (Recommended)
-   **Python 3.11+**
-   **Node.js 18+**

### 1. Environment Configuration
Create a `backend/.env` file:
```bash
# Core
SECRET_KEY=dev-secret-key-123
ALLOWED_ORIGINS=http://localhost:3000

# Database
DATABASE_URL=sqlite:///./app.db

# LLM Provider
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=mixtral-8x7b-32768

# Broker (Redis/RabbitMQ)
BROKER_URL=amqp://guest:guest@rabbitmq:5672/

# Feature Flags
COST_TRACKING_ENABLED=True
VERSIONING_ENABLED=True
```

### 2. Run with Docker (Recommended)
This starts API, Worker, DB, Redis, RabbitMQ, Jaeger, and Nginx.
```bash
docker-compose up --build -d
```
-   **Frontend**: http://localhost:3000
-   **API Docs**: http://localhost:8000/docs
-   **Jaeger UI**: http://localhost:16686

---

## 👨‍💻 Developer Guide

### Codebase Structure
```text
backend/
├── app/
│   ├── agents/         # AI Logic (Planner, Coder, etc.)
│   ├── api/            # FastAPI Routers
│   ├── costs/          # [NEW] Cost Tracking Module
│   ├── versioning/     # [NEW] Versioning & Snapshot Module
│   ├── reliability/    # [NEW] Retry & Circuit Breaker Utility
│   ├── models/         # SQLAlchemy Database Models
│   └── queue/          # Worker & Task Definitions
├── verify_*.py         # Verification Scripts for local testing
└── requirements.txt
```

### How to Add a New Tool
1.  Define the tool function in `backend/app/tools/definitions.py`.
2.  Add it to the `tools` list in the `Researcher` or `Executor` agent config.
3.  **Important**: If the tool performs writes (API POST, File Write), check for `DRY_RUN` context to ensure safety in Shadow Mode!

### Running Verifications
Test the infrastructure locally without running the full stack.

1.  **Test Versioning (Shadow Mode)**:
    ```bash
    $env:SECRET_KEY='dummy'; python backend/verify_versioning.py
    ```
2.  **Test Cost Tracking**:
    ```bash
    $env:SECRET_KEY='dummy'; python backend/verify_cost.py
    ```

---

## 🔧 Troubleshooting

**"Failed to load workflows" on Frontend?**
-   The backend container might be starting up. Check status: `docker-compose ps`.
-   Check logs: `docker-compose logs -f api`.

**"Groq Rate Limit Exceeded"?**
-   The system handles this with backoff, but you can increase the `GROQ_RATE_LIMIT` env var or switch to a different model.

---
*Built by Hardik*

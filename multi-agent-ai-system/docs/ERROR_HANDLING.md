# Error Handling & Recovery Patterns

This document describes the reliability patterns implemented in the Multi-Agent AI System to ensure robust operation, graceful degradation, and observability.

## Overview

The system employs three core patterns to handle failures:

1.  **Retries with Exponential Backoff**: For transient failures (network blips, rate limits).
2.  **Circuit Breakers**: To fail fast when a dependency (tool or API) is unhealthy, preventing cascading failures.
3.  **Checkpointing**: To save workflow state before critical steps, enabling debugging and potential recovery.

## 1. Retry Pattern

Retries are automatically applied to:
-   **LLM Calls** (Groq API)
-   **Tool Executions**

**Configuration:**
-   **Max Attempts**: Default 3
-   **Backoff**: Exponential (base 2) with jitter.
-   **Retryable Exceptions**: Network errors, timeouts, 5xx server errors (handled generically via Exception for now, excluding fatal schema errors).

**Observability:**
-   Retries are logged with warning level.
-   (Future) Tracing spans can indicate attempt counts.

## 2. Circuit Breaker Pattern

Circuit breakers prevent the system from repeatedly trying a failing operation.

**Scope:**
-   **Per Tool**: Each tool version has its own circuit breaker (e.g., `tool:web_search@1.0.0`).
-   **Per Provider**: The LLM client has a circuit breaker for the API provider (e.g., `groq_api`).

**States:**
-   **CLOSED**: Normal operation.
-   **OPEN**: Failure threshold reached. Calls fail immediately (~30-60s timeout).
-   **HALF_OPEN**: One test request is allowed to check if the service recovered.

**Configuration (Default):**
-   **Failure Threshold**: 5 consecutive failures.
-   **Recovery Timeout**: 30-60 seconds.

**Observability:**
-   Circuit state transitions are logged.
-   Spans include attributes `circuit_breaker.state` and `circuit_breaker.id`.

## 3. Checkpointing

Critical workflow steps save their state to a local SQLite database (`checkpoints.db`) before execution.

**Stored Data:**
-   `workflow_id`
-   `step` (e.g., "planner", "executor")
-   `state` (JSON serialization of agent state)
-   `timestamp`

**Usage:**
-   Debugging: Query `checkpoints.db` to see the last known good state of a failed workflow.
-   Recovery: (Future) Load checkpoint to resume workflow.

## 4. Bulkhead Isolation

Failures are isolated significantly by the distributed nature of the agents (Huey queues).
-   If the "Researcher" queue is backed up or failing, "Planner" agents continue to assume their workloads.
-   Tools are executed in isolated wrappers; a crash in a tool (e.g., generic Exception) is caught and does not crash the worker process.

## 5. Graceful Degradation & Fallbacks

When an agent fails irrecoverably (after retries):
-   The error is captured and logged.
-   The workflow status is marked as failed (currently raises exception to be caught by runner).
-   **Future Work**: Implement a "Fallback" agent or logic that detects specific failure modes and routes to manual intervention or simplified paths.

## How to Test / Verify

1.  **Logs**: Look for "Retry attempt..." or "Circuit ... OPEN" messages.
2.  **Trace**: In Jaeger, inspect spans for `circuit_breaker.state` or failure events.
3.  **DB**: sqlite3 `checkpoints.db` `SELECT * FROM checkpoints ORDER BY timestamp DESC LIMIT 5;`

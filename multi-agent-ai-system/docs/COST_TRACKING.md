# Cost Tracking & Token Optimization

This feature tracks token usage and estimates costs for all LLM calls within the system.

## Overview

-   **Granularity**: Costs are tracked per Workflow, Agent, and individual LLM Call.
-   **Storage**: Data is stored in the `llm_cost_records` database table.
-   **Observability**: Costs and token counts are visible in Jaeger traces (`llm.cost.usd`, `llm.tokens.total`).

## Configuration

Cost tracking is enabled by default. To disable it, set the environment variable:
```bash
COST_TRACKING_ENABLED=False
```

## Pricing Model

Currently, a static pricing model is used (defined in `backend/app/costs/pricing.py`).
Default example (Groq Mixtral):
-   Prompt: $0.27 / 1M tokens
-   Completion: $0.27 / 1M tokens

## Usage

### 1. Viewing Costs via Database
Query the `llm_cost_records` table to see a log of all calls.
```sql
SELECT * FROM llm_cost_records ORDER BY timestamp DESC LIMIT 10;
```

### 2. Programmatic Access
Use the `tracker` module helpers:
```python
from app.costs.tracker import get_cost_summary_by_workflow

summary = get_cost_summary_by_workflow("workflow-123")
print(f"Total Cost: ${summary['total_cost']}")
```

### 3. Tracing
Open Jaeger (http://localhost:16686) and look for spans named `llm.call` (or agent execution spans).
Check tags:
-   `llm.tokens.prompt`
-   `llm.tokens.completion`
-   `llm.cost.usd`

## Implementation Details
-   **LangChain Agents**: Uses `CostTrackingCallbackHandler` to intercept token usage from `llm_output`.
-   **Direct Groq Client**: Uses `record_llm_usage` directly in `groq_client.py`.

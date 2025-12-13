# Rate Limiting & Quota Management

## Overview

The rate limiting and quota management system provides production-grade protection for LLM provider calls with:

- **Per-provider rate limiting** using token bucket algorithm
- **Per-workflow and per-tenant quotas** to prevent runaway usage
- **Automatic provider failover** on rate limits or errors
- **Comprehensive observability** through tracing and metrics
- **Student-friendly defaults** with optional Redis backend for multi-process scaling

## Architecture

```
Client Request
     ↓
Middleware (rate_limit_middleware)
     ↓
Rate Limiter (token bucket) → Check provider tokens
     ↓
Quota Manager → Check workflow/tenant quota
     ↓
Provider Router → Select provider (primary/cost/latency policy)
     ↓
LLM Provider Call
     ↓
On Error → Failover to next provider
     ↓
Metrics & Tracing
```

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Enable/disable rate limiting
RATE_LIMIT_ENABLED=true

# Provider rate limits (requests per second)
PROVIDER_GROQ_RATE_PER_SEC=50
PROVIDER_OPENAI_RATE_PER_SEC=20

# Quota settings
QUOTA_WINDOW_DAYS=30
DEFAULT_DAILY_QUOTA_TOKENS=100000
QUOTA_ENFORCEMENT=soft  # soft|hard

# Routing policy
ROUTING_POLICY=primary  # primary|cost_weighted|latency_weighted

# Provider cooldown after errors (seconds)
PROVIDER_COOLDOWN_SEC=60

# Optional: Redis for multi-process mode
# REDIS_URL=redis://localhost:6379
```

### Configuration Options

#### Rate Limiting

- `RATE_LIMIT_ENABLED`: Enable/disable the entire system (default: `true`)
- `PROVIDER_<NAME>_RATE_PER_SEC`: Rate limit for each provider in requests per second

#### Quota Management

- `QUOTA_WINDOW_DAYS`: Rolling window for quota tracking (default: 30 days)
- `DEFAULT_DAILY_QUOTA_TOKENS`: Default token limit per workflow/tenant
- `QUOTA_ENFORCEMENT`: 
  - `soft`: Log warnings but allow over-quota requests (default, student-friendly)
  - `hard`: Reject requests that exceed quota

#### Provider Routing

- `ROUTING_POLICY`:
  - `primary`: Use highest priority provider, fallback on error
  - `cost_weighted`: Prefer cheaper providers
  - `latency_weighted`: Prefer faster providers

- `PROVIDER_COOLDOWN_SEC`: How long to mark a provider as degraded after errors

#### Multi-Process Mode

- `REDIS_URL`: If set, use Redis for accurate rate limiting across processes
- If not set, uses in-memory mode (per-process buckets)

## Usage

### Basic Usage

The rate limiting middleware is automatically applied to LLM calls:

```python
from app.llm.groq_client import call_groq_sync

# Middleware is applied automatically
result = call_groq_sync(
    prompt="Hello, world!",
    workflow_id="my-workflow",  # For quota tracking
    tenant_id="tenant-123",     # Optional
    tokens_estimate=100,        # Optional token estimate
)
```

### Manual Middleware Usage

You can also apply the middleware decorator to custom functions:

```python
from app.ratelimit.middleware import rate_limit_middleware

@rate_limit_middleware
def my_llm_call(provider_name, prompt, **kwargs):
    # Your LLM call implementation
    # provider_name is automatically injected by middleware
    return call_provider(provider_name, prompt)

# Call with metadata
result = my_llm_call(
    prompt="Hello",
    workflow_id="wf-123",
    tokens_estimate=50,
)
```

### Checking Status

Use the CLI to view current status:

```bash
# View provider token buckets and status
python manage.py ratelimit status

# View metrics (requests, rate limits, failovers)
python manage.py ratelimit metrics

# View quota for a specific workflow
python manage.py ratelimit quota my-workflow-id
```

### Programmatic Access

```python
from app.ratelimit.limiter import get_rate_limiter
from app.ratelimit.quota import get_quota_manager
from app.ratelimit.metrics import get_metrics_summary

# Check rate limiter status
limiter = get_rate_limiter()
status = limiter.get_status("groq")
print(f"Available tokens: {status['available_tokens']}")

# Check quota status
quota_manager = get_quota_manager()
quota_status = quota_manager.get_quota_status(workflow_id="my-workflow")
print(f"Quota remaining: {quota_status['tokens_remaining']}")

# Get metrics
metrics = get_metrics_summary()
print(f"Total requests: {metrics['counters'].get('llm_requests_total', 0)}")
```

## Observability

### Tracing Attributes

All LLM calls are annotated with OpenTelemetry span attributes:

- `llm.workflow_id`: Workflow identifier
- `llm.tenant_id`: Tenant identifier
- `llm.tokens_estimate`: Estimated tokens for request
- `llm.ratelimit_acquired`: Whether rate limit tokens were acquired
- `llm.ratelimit_provider`: Provider used
- `llm.ratelimit_wait_ms`: Time waited for rate limit tokens
- `llm.quota.allowed`: Whether quota check passed
- `llm.quota.remaining`: Remaining quota tokens
- `llm.routed_to`: Final provider selected
- `llm.failover_attempts`: Number of failover attempts
- `llm.rate_limited`: Whether request was rate limited
- `llm.success`: Whether request succeeded

View traces in Jaeger at `http://localhost:16686`

### Metrics

The system tracks the following metrics:

**Counters:**
- `llm_requests_total{provider, workflow_id}`: Total LLM requests
- `llm_rate_limited_total{provider}`: Rate limit events
- `llm_failovers_total{from_provider, to_provider}`: Provider failovers
- `llm_quota_exceeded_total{workflow_id, tenant_id}`: Quota exceeded events

**Gauges:**
- `provider_available_tokens{provider}`: Available tokens in bucket
- `workflow_quota_remaining_tokens{workflow_id}`: Remaining quota

**Histograms:**
- `llm_request_latency_ms{provider}`: Request latency distribution

## Provider Failover

### How It Works

1. **Primary provider fails** (rate limit, timeout, or server error)
2. **Provider marked as degraded** for cooldown period
3. **Router selects next provider** based on routing policy
4. **Request retried** with fallback provider
5. **Metrics and traces updated** with failover information

### Failover Example

```python
# Groq is primary provider
result = call_groq_sync(prompt="Hello")

# If Groq returns 429 (rate limit):
# 1. Groq marked degraded for 60 seconds
# 2. Router selects OpenAI as fallback
# 3. Request retried with OpenAI
# 4. Trace shows: llm.routed_to=openai, llm.failover_attempts=1
```

### Graceful Degradation

When all providers are exhausted or quota exceeded:

- **Soft mode**: Request proceeds with warning logged
- **Hard mode**: `QuotaExceededError` raised with structured error info

## Quota Management

### Quota Windows

Quotas are tracked in rolling time windows:

- **Daily**: `QUOTA_WINDOW_DAYS=1`
- **Monthly**: `QUOTA_WINDOW_DAYS=30`
- **Custom**: Any number of days

### Quota Enforcement Modes

#### Soft Mode (Default)

```bash
QUOTA_ENFORCEMENT=soft
```

- Logs warning when quota exceeded
- Allows request to proceed
- Annotates trace with quota status
- **Recommended for development and student use**

#### Hard Mode

```bash
QUOTA_ENFORCEMENT=hard
```

- Rejects requests that exceed quota
- Raises `QuotaExceededError`
- Returns structured error with quota info
- **Recommended for production with cost controls**

### Per-Workflow vs Per-Tenant Quotas

```python
# Per-workflow quota
call_groq_sync(prompt="Hello", workflow_id="wf-123")

# Per-tenant quota
call_groq_sync(prompt="Hello", tenant_id="tenant-456")

# Both (separate quotas)
call_groq_sync(prompt="Hello", workflow_id="wf-123", tenant_id="tenant-456")
```

## Multi-Process Mode

### In-Memory Mode (Default)

- Each process has its own token bucket
- Total rate = N × configured rate (where N = number of processes)
- **Acceptable for student use and development**

### Redis Mode (Production)

```bash
# Install Redis
docker run -d -p 6379:6379 redis

# Configure in .env
REDIS_URL=redis://localhost:6379
```

- Shared token bucket across all processes
- Accurate rate limiting
- **Recommended for production with multiple workers**

## Testing

### Run Unit Tests

```bash
# All rate limiting tests
pytest tests/ratelimit/ -v

# Specific test files
pytest tests/ratelimit/test_limiter.py -v
pytest tests/ratelimit/test_quota.py -v
pytest tests/ratelimit/test_router.py -v
```

### Test Coverage

- **Rate Limiter**: Token acquisition, refill, timeout, concurrency
- **Quota Manager**: Soft/hard modes, window rotation, multi-tenant
- **Provider Router**: Routing policies, failover, error handling

## Troubleshooting

### Rate Limiting Not Working

1. Check `RATE_LIMIT_ENABLED=true` in `.env`
2. Verify provider rate limits are set correctly
3. Check logs for rate limiter initialization

### Quota Always Exceeded

1. Check `DEFAULT_DAILY_QUOTA_TOKENS` value
2. Verify `QUOTA_WINDOW_DAYS` is appropriate
3. Use `python manage.py ratelimit quota <workflow_id>` to check status
4. Consider increasing quota or switching to soft mode

### Provider Failover Not Triggering

1. Ensure multiple providers are configured (Groq + OpenAI)
2. Check provider API keys are valid
3. Verify `PROVIDER_COOLDOWN_SEC` is reasonable
4. Check Jaeger traces for failover attributes

### Redis Connection Errors

1. Ensure Redis is running: `docker ps | grep redis`
2. Verify `REDIS_URL` is correct
3. Check Redis logs: `docker logs <redis-container-id>`
4. Fall back to in-memory mode by removing `REDIS_URL`

## Best Practices

### Development

- Use **soft mode** quota enforcement
- Set generous rate limits
- Use in-memory mode (no Redis)
- Monitor metrics via CLI

### Production

- Use **hard mode** quota enforcement
- Set realistic rate limits based on provider limits
- Use Redis mode for multi-process accuracy
- Monitor traces in Jaeger
- Set up alerts on quota exceeded metrics

### Cost Control

- Set conservative `DEFAULT_DAILY_QUOTA_TOKENS`
- Use `cost_weighted` routing policy
- Monitor quota usage regularly
- Set up alerts for high usage workflows

## Migration Guide

### Enabling Rate Limiting on Existing System

1. **Add configuration** to `.env`:
   ```bash
   RATE_LIMIT_ENABLED=true
   QUOTA_ENFORCEMENT=soft
   ```

2. **Test with soft mode** to observe behavior

3. **Monitor metrics** and adjust limits

4. **Gradually tighten** rate limits and quotas

5. **Switch to hard mode** when confident

### Disabling Rate Limiting

```bash
# In .env
RATE_LIMIT_ENABLED=false
```

All rate limiting and quota checks will be bypassed.

## API Reference

### RateLimiter

```python
from app.ratelimit.limiter import get_rate_limiter

limiter = get_rate_limiter()

# Acquire tokens
success = limiter.acquire(provider_name="groq", tokens=1, timeout=5.0)

# Release tokens (for cancellation)
limiter.release(provider_name="groq", tokens=1)

# Get status
status = limiter.get_status(provider_name="groq")
# Returns: {available_tokens, rate_per_sec, max_tokens, enabled}
```

### QuotaManager

```python
from app.ratelimit.quota import get_quota_manager

quota_manager = get_quota_manager()

# Check and reserve
allowed = quota_manager.check_and_reserve(
    workflow_id="wf-123",
    tenant_id="tenant-456",
    tokens=100
)

# Get status
status = quota_manager.get_quota_status(workflow_id="wf-123")
# Returns: {tokens_used, tokens_remaining, tokens_limit, window_start, window_end, reset_at}
```

### ProviderRouter

```python
from app.ratelimit.router import get_provider_router

router = get_provider_router()

# Select provider
provider = router.select_provider(
    workflow_id="wf-123",
    preferred_provider="groq"
)

# Execute with failover
result = router.execute_with_failover(
    func=my_llm_call,
    workflow_id="wf-123",
    max_attempts=3
)
```

## Examples

See `examples/ratelimit_demo.py` for complete usage examples.

## Support

For issues or questions:
1. Check this documentation
2. Review test files for usage examples
3. Check Jaeger traces for debugging
4. Use CLI tools to inspect status

"""
CLI Management Script for Rate Limiting

Provides commands to view rate limiter status, quota usage, and metrics.

Usage:
    python manage.py ratelimit status
    python manage.py ratelimit metrics
    python manage.py ratelimit quota <workflow_id>
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ratelimit.config import load_rate_limit_config
from app.ratelimit.limiter import get_rate_limiter
from app.ratelimit.quota import get_quota_manager
from app.ratelimit.router import ProviderRegistry
from app.ratelimit.metrics import get_metrics_summary
from app.hitl.cli import handle_hitl_command


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


def cmd_status():
    """Display rate limiter and provider status."""
    print_header("Rate Limiting Status")
    
    config = load_rate_limit_config()
    limiter = get_rate_limiter()
    
    print(f"Rate Limiting: {'ENABLED' if config.enabled else 'DISABLED'}")
    print(f"Routing Policy: {config.routing_policy}")
    print(f"Quota Enforcement: {config.quota_enforcement}")
    print(f"Redis Backend: {'YES' if config.redis_url else 'NO (in-memory)'}")
    
    print("\n" + "-" * 60)
    print("Provider Token Buckets:")
    print("-" * 60)
    
    providers = ["groq", "openai"]
    
    for provider in providers:
        status = limiter.get_status(provider)
        is_degraded = ProviderRegistry.is_degraded(provider)
        
        print(f"\n{provider.upper()}:")
        print(f"  Available Tokens: {status.get('available_tokens', 'N/A')}")
        print(f"  Rate Limit: {status.get('rate_per_sec', 'N/A')} req/sec")
        print(f"  Max Tokens: {status.get('max_tokens', 'N/A')}")
        print(f"  Status: {'DEGRADED' if is_degraded else 'HEALTHY'}")
    
    print("\n")


def cmd_metrics():
    """Display metrics summary."""
    print_header("Rate Limiting Metrics")
    
    metrics = get_metrics_summary()
    
    print("Counters:")
    print("-" * 60)
    for key, value in sorted(metrics.get("counters", {}).items()):
        print(f"  {key}: {value}")
    
    print("\nGauges:")
    print("-" * 60)
    for key, value in sorted(metrics.get("gauges", {}).items()):
        print(f"  {key}: {value}")
    
    print("\nHistograms:")
    print("-" * 60)
    for key, stats in sorted(metrics.get("histograms", {}).items()):
        if stats:
            print(f"  {key}:")
            print(f"    Count: {stats.get('count', 0)}")
            print(f"    Avg: {stats.get('avg', 0):.2f}")
            print(f"    P50: {stats.get('p50', 0):.2f}")
            print(f"    P95: {stats.get('p95', 0):.2f}")
            print(f"    P99: {stats.get('p99', 0):.2f}")
    
    metadata = metrics.get("metadata", {})
    print(f"\nUptime: {metadata.get('uptime_seconds', 0):.2f} seconds")
    print()


def cmd_quota(workflow_id: str = None):
    """Display quota status for a workflow."""
    print_header(f"Quota Status{' for ' + workflow_id if workflow_id else ''}")
    
    quota_manager = get_quota_manager()
    status = quota_manager.get_quota_status(workflow_id=workflow_id)
    
    if status.get("enabled"):
        print(f"Tokens Used: {status.get('tokens_used', 0)}")
        print(f"Tokens Remaining: {status.get('tokens_remaining', 0)}")
        print(f"Tokens Limit: {status.get('tokens_limit', 0)}")
        print(f"Window Start: {status.get('window_start', 'N/A')}")
        print(f"Window End: {status.get('window_end', 'N/A')}")
        print(f"Reset At: {status.get('reset_at', 'N/A')}")
        print(f"Enforcement Mode: {status.get('enforcement_mode', 'N/A')}")
    else:
        print("Quota tracking is DISABLED")
    
    print()


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python manage.py <domain> <command>")
        print("\nDomains:")
        print("  ratelimit  - Rate limiting commands")
        print("  hitl       - Human-in-the-Loop commands")
        sys.exit(1)
    
    domain = sys.argv[1]
    
    if domain == "ratelimit":
        if len(sys.argv) < 3:
            print("Usage: python manage.py ratelimit <command>")
            sys.exit(1)
        
        command = sys.argv[2]
        if command == "status":
            cmd_status()
        elif command == "metrics":
            cmd_metrics()
        elif command == "quota":
            workflow_id = sys.argv[3] if len(sys.argv) > 3 else None
            cmd_quota(workflow_id)
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    
    elif domain == "hitl":
        handle_hitl_command()
        
    else:
        print(f"Unknown domain: {domain}")
        sys.exit(1)

if __name__ == "__main__":
    main()

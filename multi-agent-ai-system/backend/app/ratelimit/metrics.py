"""
Metrics Collection for Rate Limiting

Tracks counters and gauges for rate limiting, quota, and routing decisions.
In-memory implementation with thread-safe updates.
"""

import logging
import threading
from typing import Dict, Any, Optional
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


class MetricsCollector:
    """
    Thread-safe metrics collector for rate limiting.
    
    Tracks:
    - Request counts by provider and workflow
    - Rate limit events
    - Failover events
    - Provider token availability
    - Quota remaining
    """
    
    def __init__(self):
        """Initialize metrics collector."""
        self.lock = threading.Lock()
        
        # Counters
        self.counters = defaultdict(int)
        
        # Gauges (latest value)
        self.gauges = {}
        
        # Histograms (for latency tracking)
        self.histograms = defaultdict(list)
        
        # Metadata
        self.start_time = datetime.utcnow()
    
    def increment_counter(self, name: str, labels: Optional[Dict[str, str]] = None, value: int = 1):
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            labels: Optional labels dict
            value: Increment value (default: 1)
        """
        key = self._make_key(name, labels)
        
        with self.lock:
            self.counters[key] += value
    
    def set_gauge(self, name: str, labels: Optional[Dict[str, str]] = None, value: float = 0):
        """
        Set a gauge metric value.
        
        Args:
            name: Metric name
            labels: Optional labels dict
            value: Gauge value
        """
        key = self._make_key(name, labels)
        
        with self.lock:
            self.gauges[key] = value
    
    def observe_histogram(self, name: str, labels: Optional[Dict[str, str]] = None, value: float = 0):
        """
        Add an observation to a histogram.
        
        Args:
            name: Metric name
            labels: Optional labels dict
            value: Observed value
        """
        key = self._make_key(name, labels)
        
        with self.lock:
            self.histograms[key].append(value)
            
            # Keep only last 1000 observations to prevent memory bloat
            if len(self.histograms[key]) > 1000:
                self.histograms[key] = self.histograms[key][-1000:]
    
    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> int:
        """Get counter value."""
        key = self._make_key(name, labels)
        
        with self.lock:
            return self.counters.get(key, 0)
    
    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get gauge value."""
        key = self._make_key(name, labels)
        
        with self.lock:
            return self.gauges.get(key)
    
    def get_histogram_stats(self, name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get histogram statistics (min, max, avg, p50, p95, p99)."""
        key = self._make_key(name, labels)
        
        with self.lock:
            values = self.histograms.get(key, [])
            
            if not values:
                return {}
            
            sorted_values = sorted(values)
            count = len(sorted_values)
            
            return {
                "count": count,
                "min": sorted_values[0],
                "max": sorted_values[-1],
                "avg": sum(sorted_values) / count,
                "p50": sorted_values[int(count * 0.5)],
                "p95": sorted_values[int(count * 0.95)],
                "p99": sorted_values[int(count * 0.99)],
            }
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics as a dict."""
        with self.lock:
            return {
                "counters": dict(self.counters),
                "gauges": dict(self.gauges),
                "histograms": {
                    key: self.get_histogram_stats(key.split(":")[0], self._parse_labels(key))
                    for key in self.histograms.keys()
                },
                "metadata": {
                    "start_time": self.start_time.isoformat(),
                    "uptime_seconds": (datetime.utcnow() - self.start_time).total_seconds(),
                },
            }
    
    def reset_metrics(self):
        """Reset all metrics (useful for testing)."""
        with self.lock:
            self.counters.clear()
            self.gauges.clear()
            self.histograms.clear()
            self.start_time = datetime.utcnow()
    
    @staticmethod
    def _make_key(name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Create a unique key from metric name and labels."""
        if not labels:
            return name
        
        # Sort labels for consistent keys
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}:{label_str}"
    
    @staticmethod
    def _parse_labels(key: str) -> Optional[Dict[str, str]]:
        """Parse labels from a metric key."""
        if ":" not in key:
            return None
        
        _, label_str = key.split(":", 1)
        labels = {}
        
        for pair in label_str.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                labels[k] = v
        
        return labels if labels else None


# Global metrics collector
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """
    Get the global metrics collector instance.
    
    Returns:
        MetricsCollector instance
    """
    global _metrics_collector
    
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    
    return _metrics_collector


# Convenience functions for common metrics

def record_llm_request(provider: str, workflow_id: Optional[str] = None):
    """Record an LLM request."""
    collector = get_metrics_collector()
    
    labels = {"provider": provider}
    if workflow_id:
        labels["workflow_id"] = workflow_id
    
    collector.increment_counter("llm_requests_total", labels)


def record_rate_limited(provider: str):
    """Record a rate limit event."""
    collector = get_metrics_collector()
    collector.increment_counter("llm_rate_limited_total", {"provider": provider})


def record_failover(from_provider: str, to_provider: str):
    """Record a provider failover."""
    collector = get_metrics_collector()
    collector.increment_counter("llm_failovers_total", {
        "from_provider": from_provider,
        "to_provider": to_provider,
    })


def record_quota_exceeded(workflow_id: Optional[str] = None, tenant_id: Optional[str] = None):
    """Record a quota exceeded event."""
    collector = get_metrics_collector()
    
    labels = {}
    if workflow_id:
        labels["workflow_id"] = workflow_id
    if tenant_id:
        labels["tenant_id"] = tenant_id
    
    collector.increment_counter("llm_quota_exceeded_total", labels)


def update_provider_tokens(provider: str, available_tokens: int):
    """Update provider available tokens gauge."""
    collector = get_metrics_collector()
    collector.set_gauge("provider_available_tokens", {"provider": provider}, available_tokens)


def update_quota_remaining(workflow_id: str, remaining_tokens: int):
    """Update workflow quota remaining gauge."""
    collector = get_metrics_collector()
    collector.set_gauge("workflow_quota_remaining_tokens", {"workflow_id": workflow_id}, remaining_tokens)


def record_request_latency(provider: str, latency_ms: float):
    """Record request latency."""
    collector = get_metrics_collector()
    collector.observe_histogram("llm_request_latency_ms", {"provider": provider}, latency_ms)


def get_metrics_summary() -> Dict[str, Any]:
    """
    Get a summary of all metrics.
    
    Returns:
        Dict with metrics summary
    """
    collector = get_metrics_collector()
    return collector.get_all_metrics()

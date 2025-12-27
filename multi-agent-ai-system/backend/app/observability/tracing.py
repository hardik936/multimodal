"""
Centralized Tracing Utility for Distributed Tracing

Provides OpenTelemetry-based tracing with Jaeger as the default backend.
Supports configuration via environment variables and safe failure handling.
"""

import os
import logging
from typing import Optional
from contextlib import contextmanager

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.trace import Status, StatusCode, Tracer
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("Opentelemetry not installed. Tracing will be disabled.")
    OPENTELEMETRY_AVAILABLE = False
    
    # Mocks for missing classes
    class Tracer:
        def start_as_current_span(self, name):
            from contextlib import contextmanager
            @contextmanager
            def noop_span():
                yield None
            return noop_span()
            
    class TracerProvider:
        def __init__(self, resource=None): pass
        def add_span_processor(self, processor): pass
        
    class BatchSpanProcessor:
        def __init__(self, exporter): pass
        
    class JaegerExporter:
        def __init__(self, agent_host_name, agent_port): pass
        
    class Resource:
        def __init__(self, attributes): pass
        
    SERVICE_NAME = "service_name"
    
    class Status:
        def __init__(self, status_code, description): pass
        
    class StatusCode:
        ERROR = "ERROR"
        
    class trace:
        @staticmethod
        def get_tracer(name):
            return Tracer()
        
        @staticmethod
        def set_tracer_provider(provider): pass

logger = logging.getLogger(__name__)

# Global tracer provider
_tracer_provider: Optional[TracerProvider] = None
_tracing_configured = False


def configure_tracing():
    """
    Configure OpenTelemetry tracing with Jaeger exporter.
    
    Environment Variables:
    - TRACING_ENABLED: Enable/disable tracing (default: true)
    - TRACING_EXPORTER: Exporter type (default: jaeger)
    - TRACING_SERVICE_NAME: Service name (default: multi-agent-ai-system)
    - JAEGER_AGENT_HOST: Jaeger agent host (default: localhost)
    - JAEGER_AGENT_PORT: Jaeger agent port (default: 6831)
    
    Safe Failure: If configuration fails, tracing is disabled but app continues.
    """
    global _tracer_provider, _tracing_configured
    
    if not OPENTELEMETRY_AVAILABLE:
        _tracing_configured = True
        return

    if _tracing_configured:
        return
    
    try:
        # Check if tracing is enabled
        tracing_enabled = os.getenv("TRACING_ENABLED", "true").lower() == "true"
        
        if not tracing_enabled:
            logger.info("Tracing is disabled via TRACING_ENABLED=false")
            _tracing_configured = True
            return
        
        # Get configuration
        service_name = os.getenv("TRACING_SERVICE_NAME", "multi-agent-ai-system")
        exporter_type = os.getenv("TRACING_EXPORTER", "jaeger").lower()
        
        # Create resource with service name
        resource = Resource(attributes={
            SERVICE_NAME: service_name
        })
        
        # Create tracer provider
        _tracer_provider = TracerProvider(resource=resource)
        
        # Configure exporter
        if exporter_type == "jaeger":
            jaeger_host = os.getenv("JAEGER_AGENT_HOST", "localhost")
            jaeger_port = int(os.getenv("JAEGER_AGENT_PORT", "6831"))
            
            jaeger_exporter = JaegerExporter(
                agent_host_name=jaeger_host,
                agent_port=jaeger_port,
            )
            
            # Use batch processor for async export
            span_processor = BatchSpanProcessor(jaeger_exporter)
            _tracer_provider.add_span_processor(span_processor)
            
            logger.info(f"Jaeger tracing configured: {jaeger_host}:{jaeger_port}")
        
        elif exporter_type == "console":
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            console_exporter = ConsoleSpanExporter()
            span_processor = BatchSpanProcessor(console_exporter)
            _tracer_provider.add_span_processor(span_processor)
            logger.info("Console tracing configured")
        
        elif exporter_type == "none":
            logger.info("Tracing exporter set to 'none' - no spans will be exported")
        
        else:
            logger.warning(f"Unknown exporter type: {exporter_type}. Tracing disabled.")
            _tracer_provider = None
        
        # Set global tracer provider
        if _tracer_provider:
            trace.set_tracer_provider(_tracer_provider)
        
        _tracing_configured = True
        logger.info(f"Tracing configured successfully (service: {service_name})")
    
    except Exception as e:
        logger.error(f"Failed to configure tracing: {e}. Tracing will be disabled.")
        _tracer_provider = None
        _tracing_configured = True


def is_tracing_enabled() -> bool:
    """
    Check if tracing is enabled.
    
    Returns:
        True if tracing is configured and enabled, False otherwise
    """
    return _tracer_provider is not None


def get_tracer(service_name: str) -> Tracer:
    """
    Get a tracer for the given service name.
    
    Args:
        service_name: Name of the service/component
    
    Returns:
        Tracer instance (may be a no-op tracer if tracing is disabled)
    """
    # Ensure tracing is configured
    if not _tracing_configured:
        configure_tracing()
    
    # Return tracer (will be no-op if tracing is disabled)
    return trace.get_tracer(service_name)


@contextmanager
def trace_span(
    tracer: Tracer,
    span_name: str,
    attributes: Optional[dict] = None,
    set_status_on_exception: bool = True
):
    """
    Context manager for creating a traced span with safe error handling.
    
    Args:
        tracer: Tracer instance
        span_name: Name of the span
        attributes: Optional span attributes
        set_status_on_exception: Whether to mark span as error on exception
    
    Yields:
        Span instance
    
    Example:
        with trace_span(tracer, "my_operation", {"key": "value"}) as span:
            # Do work
            span.set_attribute("result", "success")
    """
    if not is_tracing_enabled():
        # No-op context manager when tracing is disabled
        yield None
        return
    
    try:
        with tracer.start_as_current_span(span_name) as span:
            # Set attributes if provided
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            
            try:
                yield span
            except Exception as e:
                if set_status_on_exception and span:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                raise
    
    except Exception as e:
        # Safe failure: log error but don't crash
        logger.error(f"Error in trace_span '{span_name}': {e}")
        yield None


def set_span_error(span, error: Exception):
    """
    Mark a span as errored with exception details.
    
    Args:
        span: Span instance
        error: Exception that occurred
    """
    if span and is_tracing_enabled():
        try:
            span.set_status(Status(StatusCode.ERROR, str(error)))
            span.record_exception(error)
        except Exception as e:
            logger.error(f"Error setting span error: {e}")


def add_span_attributes(span, attributes: dict):
    """
    Add attributes to a span safely.
    
    Args:
        span: Span instance
        attributes: Dictionary of attributes to add
    """
    if span and is_tracing_enabled():
        try:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        except Exception as e:
            logger.error(f"Error adding span attributes: {e}")

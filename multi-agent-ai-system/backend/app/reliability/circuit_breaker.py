import time
import logging
from enum import Enum
from typing import Optional, Dict, Any
from app.observability.tracing import get_tracer, trace_span, add_span_attributes

logger = logging.getLogger(__name__)
tracer = get_tracer("reliability.circuit_breaker")

class CircuitState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreakerOpenException(Exception):
    """Raised when a call is attempting to be made while the circuit is open."""
    pass

class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exceptions: list = None
    ):
        """
        Circuit Breaker implementation.
        
        Args:
            name: Identifier for this circuit breaker.
            failure_threshold: Number of failures before opening the circuit.
            recovery_timeout: Seconds to wait before attempting recovery (HALF_OPEN).
            expected_exceptions: List of exception types that count as failures.
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions or [Exception]
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
    
    def call(self, func, *args, **kwargs):
        """
        Executes the function wrapped in circuit breaker logic.
        """
        self._before_call()
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            if self._is_exception_relevant(e):
                self._on_failure()
            raise e

    def _is_exception_relevant(self, exception: Exception) -> bool:
        return any(isinstance(exception, exc_type) for exc_type in self.expected_exceptions)

    def _before_call(self):
        """
        Logic to run before calling the protected function.
        Check if circuit is open and if timeout has passed.
        """
        current_time = time.time()
        
        if self.state == CircuitState.OPEN:
            if current_time - self.last_failure_time > self.recovery_timeout:
                self._transition_to(CircuitState.HALF_OPEN)
                logger.info(f"Circuit '{self.name}' probe engaged (HALF_OPEN).")
            else:
                # Circuit is still open and timeout hasn't passed
                msg = f"Circuit '{self.name}' is OPEN. failures={self.failure_count}"
                logger.warning(msg)
                raise CircuitBreakerOpenException(msg)
    
    def _on_success(self):
        """
        Logic to run on successful execution.
        """
        if self.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.CLOSED)
            logger.info(f"Circuit '{self.name}' recovered (CLOSED).")
        
        # Reset counters on success
        self.failure_count = 0

    def _on_failure(self):
        """
        Logic to run on execution failure.
        """
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            # If we fail in half-open, immediately reopen
            self._transition_to(CircuitState.OPEN)
            logger.warning(f"Circuit '{self.name}' probe failed. Re-opening.")
            
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self._transition_to(CircuitState.OPEN)
                logger.error(f"Circuit '{self.name}' threshold reached. OPENING.")

    def _transition_to(self, new_state: CircuitState):
        self.state = new_state
        # Trace state change?
        
    def get_state_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "last_failure_time": self.last_failure_time
        }

# Global registry to hold circuit breakers by name
_breakers = {}

def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    if name not in _breakers:
        _breakers[name] = CircuitBreaker(name, **kwargs)
    return _breakers[name]

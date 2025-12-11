import time
import logging
from app.reliability.retry import retry_with_backoff
from app.reliability.circuit_breaker import get_circuit_breaker, CircuitBreakerOpenException, CircuitState
from app.reliability.checkpoint import save_checkpoint, load_last_checkpoint

# Configure simple logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("verification")

def verify_retry():
    logger.info("--- Verifying Retry ---")
    attempts = 0
    
    @retry_with_backoff(max_attempts=3, initial_delay=0.1, jitter=False)
    def failing_function():
        nonlocal attempts
        attempts += 1
        logger.info(f"Function called (Attempt {attempts})")
        raise ValueError("Simulated Failure")

    try:
        failing_function()
    except ValueError:
        logger.info("Function failed as expected after retries.")
    
    if attempts == 3:
        logger.info("PASS: Retry logic attempted 3 times.")
    else:
        logger.error(f"FAIL: Expected 3 attempts, got {attempts}")

def verify_circuit_breaker():
    logger.info("\n--- Verifying Circuit Breaker ---")
    cb_name = "test_breaker"
    cb = get_circuit_breaker(cb_name, failure_threshold=2, recovery_timeout=1)
    
    # 1. Fail twice to open circuit
    logger.info("Triggering failures...")
    try: cb.call(lambda: (_ for _ in ()).throw(ValueError("Fail 1")))
    except: pass
    try: cb.call(lambda: (_ for _ in ()).throw(ValueError("Fail 2")))
    except: pass
    
    # 2. Verify Open
    if cb.state == CircuitState.OPEN:
        logger.info("PASS: Circuit is OPEN after threshold.")
    else:
        logger.error(f"FAIL: Circuit should be OPEN, is {cb.state}")
        return

    # 3. Verify Fast Fail
    try:
        cb.call(lambda: print("Should not run"))
        logger.error("FAIL: Should have raised CircuitBreakerOpenException")
    except CircuitBreakerOpenException:
        logger.info("PASS: Circuit blocked call immediately.")
    
    # 4. Wait for recovery
    logger.info("Waiting for recovery timeout (1.1s)...")
    time.sleep(1.1)
    
    # 5. Verify Half-Open / Recovery
    # Next call should be allowed (Half-Open)
    # We'll make it succeed
    try:
        cb.call(lambda: logger.info("Recovery call succeeded!"))
        if cb.state == CircuitState.CLOSED:
             logger.info("PASS: Circuit recovered to CLOSED.")
        else:
             logger.error(f"FAIL: Circuit should be CLOSED after success, is {cb.state}")
    except Exception as e:
        logger.error(f"FAIL: Recovery call failed: {e}")

def verify_checkpoint():
    logger.info("\n--- Verifying Checkpointing ---")
    wf_id = "test_workflow_123"
    
    state = {"foo": "bar", "complex": [1, 2, 3]}
    save_checkpoint(wf_id, "step_1", state)
    
    loaded = load_last_checkpoint(wf_id)
    if loaded and loaded["state"] == state:
        logger.info("PASS: Checkpoint saved and loaded correctly.")
    else:
        logger.error(f"FAIL: Loaded state does not match. Got {loaded}")

if __name__ == "__main__":
    verify_retry()
    verify_circuit_breaker()
    verify_checkpoint()

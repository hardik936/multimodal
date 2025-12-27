import docker
import time
import logging
from app.execution.sandbox import ExecutionService, ExecutionResult

logger = logging.getLogger(__name__)

class DockerSandbox(ExecutionService):
    def __init__(self, image: str = "python:3.10-slim"):
        self.image = image
        try:
            self.client = docker.from_env()
            # Ensure image exists
            # self.client.images.pull(self.image) # Optional: Pull on init or run
        except Exception as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            self.client = None

    def execute_code(self, language: str, code: str, timeout: int = 30) -> ExecutionResult:
        if not self.client:
            return ExecutionResult(
                stdout="",
                stderr="Docker client not initialized. Is Docker running?",
                exit_code=-1,
                duration_ms=0
            )

        if language.lower() not in ["python", "python3"]:
            return ExecutionResult(
                stdout="",
                stderr=f"Unsupported language: {language}",
                exit_code=-1,
                duration_ms=0
            )

        container = None
        start_time = time.time()
        try:
            # Create a simple command to execute the code
            # We pass the code as a string to python -c
            # WARNING: This has limitations with quotes. Better to mount or echo to file.
            # Using echo to file and then running it is safer for complex scripts.
            
            # Use 'sh -c' to handle file creation and execution
            # Escape single quotes in code?
            # Actually, detach=True and pass command
            
            # Robust way: 
            # command = ["python", "-c", code] -> works if code doesn't have args issues.
            
            # Let's try writing to a file inside the container
            # 'cat <<EOF > script.py ... EOF' is brittle.
            
            # Using docker client 'exec_run' on a standing container is faster but stateful.
            # We want ephemeral.
            
            # Best: containers.run(detach=True, command=["python", "-c", code])
            container = self.client.containers.run(
                self.image,
                command=["python", "-c", code],
                detach=True,
                mem_limit="128m",
                network_disabled=True, # Security
                # pids_limit=10, # Prevent fork bombs - requires newer docker
            )
            
            # Wait for result or timeout
            # containers.get().wait() blocks?
            
            # Poll for status
            elapsed = 0
            while container.status in ['created', 'running', 'restarting']:
                container.reload()
                if container.status == 'exited':
                    break
                time.sleep(0.1)
                elapsed += 0.1
                if elapsed > timeout:
                    container.kill()
                    return ExecutionResult(
                        stdout="",
                        stderr="Execution timed out",
                        exit_code=-1,
                        duration_ms=elapsed * 1000
                    )
            
            result = container.wait()
            exit_code = result.get('StatusCode', 0)
            logs = container.logs(stdout=True, stderr=True) # Returns bytes, mixed
            
            # Separate stdout/stderr if possible? 
            # docker SDK returns combined if stream=False usually, or generic bytes.
            # container.logs(stdout=True, stderr=False) -> stdout
            
            stdout_params = container.logs(stdout=True, stderr=False).decode('utf-8')
            stderr_params = container.logs(stdout=False, stderr=True).decode('utf-8')
            
            duration = (time.time() - start_time) * 1000
            
            return ExecutionResult(
                stdout=stdout_params,
                stderr=stderr_params,
                exit_code=exit_code,
                duration_ms=duration
            )
            
        except Exception as e:
            logger.error(f"Docker execution failed: {e}")
            return ExecutionResult(
                stdout="",
                stderr=str(e),
                exit_code=-1,
                duration_ms=(time.time() - start_time) * 1000
            )
        finally:
            if container:
                try:
                    container.remove(force=True)
                except:
                    pass

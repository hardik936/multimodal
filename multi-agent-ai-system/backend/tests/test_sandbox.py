import pytest
from unittest.mock import MagicMock, patch
from app.execution.docker_runner import DockerSandbox, ExecutionResult

@pytest.fixture
def mock_docker_client():
    with patch("docker.from_env") as mock_from_env:
        mock_client = MagicMock()
        mock_from_env.return_value = mock_client
        yield mock_client

def test_sandbox_init_fails(mock_docker_client):
    mock_docker_client.side_effect = Exception("Docker not running")
    with patch("docker.from_env", side_effect=Exception("Docker down")):
        sandbox = DockerSandbox()
        assert sandbox.client is None
        res = sandbox.execute_code("python", "print('hi')")
        assert res.exit_code == -1
        assert "not initialized" in res.stderr

def test_sandbox_execute_success(mock_docker_client):
    sandbox = DockerSandbox()
    
    mock_container = MagicMock()
    mock_container.status = 'exited'
    mock_container.wait.return_value = {'StatusCode': 0}
    # logs returns bytes. tuple (stdout, stderr) or mixed? 
    # In my impl I call it twice with stdout=True/False
    # Mock logs side effect based on kwargs
    def logs_side_effect(stdout=False, stderr=False):
        if stdout and not stderr:
            return b"Hello World\n"
        if stderr and not stdout:
            return b""
        return b"Hello World\n"
        
    mock_container.logs.side_effect = logs_side_effect
    
    mock_docker_client.containers.run.return_value = mock_container
    
    res = sandbox.execute_code("python", "print('hello')")
    
    assert res.exit_code == 0
    assert "Hello World" in res.stdout
    assert res.stderr == ""
    
    mock_docker_client.containers.run.assert_called_once()
    args, kwargs = mock_docker_client.containers.run.call_args
    assert "python:3.10-slim" == args[0]
    assert kwargs['command'] == ["python", "-c", "print('hello')"]

def test_sandbox_execute_timeout(mock_docker_client):
    sandbox = DockerSandbox()
    
    # Simulate container taking too long
    mock_container = MagicMock()
    # status toggles: running -> running -> ...
    mock_container.status = 'running'
    mock_container.reload.side_effect = None
    
    mock_docker_client.containers.run.return_value = mock_container
    
    # Short timeout for test
    res = sandbox.execute_code("python", "while True: pass", timeout=0.1)
    
    assert res.exit_code == -1
    assert "timed out" in res.stderr
    mock_container.kill.assert_called_once()

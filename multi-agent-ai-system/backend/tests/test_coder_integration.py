import pytest
from unittest.mock import MagicMock, patch
from app.agents.coder import coder_node
from app.execution.docker_runner import ExecutionResult

# Mock the entire sandbox module to avoid real docker calls
@pytest.fixture
def mock_sandbox():
    # Patch where it is defined/imported FROM, because it is locally imported in coder_node
    with patch("app.execution.docker_runner.DockerSandbox") as MockSandbox:
        instance = MockSandbox.return_value
        instance.client = MagicMock() # Simulate active client
        yield instance

@pytest.fixture
def mock_llm_chain():
    # We need to mock the LLM chain used inside coder_node
    # coder_node uses: chain = prompt | llm
    # And also: fix_chain = correction_prompt | llm
    
    with patch("app.agents.coder.ChatGroq") as mock_llm_cls:
        mock_llm = mock_llm_cls.return_value
        
        # We need to mock the chain.invoke() result.
        # Since chain is constructed via `prompt | llm`, it's a RunnableBinding or similar.
        # It's easier to mock the `chain` variable if we could, but it's local.
        # Instead, we mock langchain_core.prompts.ChatPromptTemplate.from_template returning a mock that produces a mock chain?
        # Or mock the `invoke` method of the object returned by `|`.
        
        # Simpler approach: Mock `ChatGroq` methods if used directly, but here it's piped.
        # Let's mock `langchain_groq.ChatGroq` to return an object that acts as the runnable.
        
        # Actually, `chain = prompt | llm`. The result is a Runnable.
        # Calling invoke on it calls logical steps.
        
        # Let's mock the `invoke` method of the chain. 
        # But we can't easily catch the *exact* chain object created inside.
        
        # ALTERNATIVE: Mock `app.agents.coder.ChatPromptTemplate` 
        # and make `prompt | llm` return our MockChain.
        
        mock_chain = MagicMock()
        
        # Side effect to handle normal generation vs fix generation
        def invoke_side_effect(input_dict, config=None):
            # Check input to distinguish
            if "code" in input_dict and "error" in input_dict:
                # This is the FIX request
                return MagicMock(content="```python\n# Fixed code\nprint('fixed')\n```")
            else:
                # This is initial generation
                return MagicMock(content="```python\n# Bad code\nprint('error')\n```")
        
        mock_chain.invoke.side_effect = invoke_side_effect
        
        # We need `prompt | llm` to return `mock_chain`
        # `prompt` is created via `ChatPromptTemplate.from_template(...)`
        with patch("app.agents.coder.ChatPromptTemplate") as mock_prompt_cls:
            mock_prompt = mock_prompt_cls.from_template.return_value
            mock_prompt.__or__.return_value = mock_chain # prompt | llm -> chain
            
            yield mock_chain

def test_coder_retries_on_failure(mock_sandbox, mock_llm_chain):
    # Setup sandbox to fail first, then succeed
    
    # 1. First call (Bad code) -> Fails
    # 2. Second call (Fixed code) -> Succeeds
    
    def execute_side_effect(language, code, timeout=30):
        if "print('error')" in code:
            return ExecutionResult(stdout="", stderr="SyntaxError: bad", exit_code=1, duration_ms=10)
        else:
            return ExecutionResult(stdout="fixed", stderr="", exit_code=0, duration_ms=10)
            
    mock_sandbox.execute_code.side_effect = execute_side_effect
    
    state = {
        "input": "Write a script",
        "language": "python",
        "execution_data": "Do it",
        "query_complexity": "COMPLEX"
    }
    
    result = coder_node(state)
    
    # Verify we got the fixed code
    assert "Fixed code" in result["code_data"]
    
    # Verify verification note was appended
    assert "Verification: Code ran successfully" in result["code_data"]
    
    # Verify execute_code called twice
    assert mock_sandbox.execute_code.call_count == 2
    
def test_coder_skips_verification_for_non_python(mock_sandbox, mock_llm_chain):
    # Clear fixture side_effect so return_value works
    mock_llm_chain.invoke.side_effect = None
    # Set chain to return valid JS
    mock_llm_chain.invoke.return_value = MagicMock(content="console.log('hi')")
    
    state = {
        "input": "Write JS",
        "language": "javascript",
        "query_complexity": "COMPLEX"
    }
    
    result = coder_node(state)
    
    # Should contain original code
    assert "console.log('hi')" in result["code_data"]
    
    # Should NOT have called sandbox (only python supported in this impl)
    mock_sandbox.execute_code.assert_not_called()

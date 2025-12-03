import pytest
from unittest.mock import patch, MagicMock
import time
from app.llm import groq_client
from app.config import settings

# Mock the Groq client
@pytest.fixture
def mock_groq():
    with patch("app.llm.groq_client.Groq") as mock:
        yield mock

@pytest.fixture
def mock_chat_groq():
    with patch("app.llm.groq_client.ChatGroq") as mock:
        yield mock

def test_get_groq_llm_success(mock_chat_groq):
    settings.GROQ_API_KEY = "test_key"
    settings.GROQ_MODEL = "test_model"
    
    llm = groq_client.get_groq_llm()
    
    mock_chat_groq.assert_called_once_with(
        groq_api_key="test_key",
        model_name="test_model",
        temperature=0.7,
        max_tokens=2000
    )

def test_get_groq_llm_no_key():
    settings.GROQ_API_KEY = None
    with pytest.raises(ValueError, match="GROQ_API_KEY is not set"):
        groq_client.get_groq_llm()

def test_call_groq_sync_success(mock_groq):
    settings.GROQ_API_KEY = "test_key"
    
    mock_instance = mock_groq.return_value
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Test response"
    mock_instance.chat.completions.create.return_value = mock_response
    
    response = groq_client.call_groq_sync("Test prompt")
    
    assert response == "Test response"
    mock_instance.chat.completions.create.assert_called_once()
    call_args = mock_instance.chat.completions.create.call_args
    assert call_args.kwargs["messages"][0]["content"] == "Test prompt"

def test_rate_limiter():
    # Reset timestamps
    groq_client._request_timestamps = []
    
    # Set limit to 2 per minute
    original_limit = settings.GROQ_RATE_LIMIT
    settings.GROQ_RATE_LIMIT = 2
    
    try:
        # Mock time.sleep to avoid waiting but verify it was called
        with patch("time.sleep") as mock_sleep:
            # 1st call
            groq_client.rate_limit_groq(lambda: None)()
            # 2nd call
            groq_client.rate_limit_groq(lambda: None)()
            
            assert mock_sleep.call_count == 0
            
            # 3rd call should trigger sleep
            groq_client.rate_limit_groq(lambda: None)()
            
            assert mock_sleep.call_count == 1
    finally:
        settings.GROQ_RATE_LIMIT = original_limit

def test_caching(mock_groq):
    settings.GROQ_API_KEY = "test_key"
    
    # Reset cache
    groq_client._cached_groq_call.cache_clear()
    
    mock_instance = mock_groq.return_value
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Cached response"
    mock_instance.chat.completions.create.return_value = mock_response
    
    # Call twice
    res1 = groq_client.call_with_cache("Repeat prompt")
    res2 = groq_client.call_with_cache("Repeat prompt")
    
    assert res1 == "Cached response"
    assert res2 == "Cached response"
    
    # Should only be called once
    assert mock_instance.chat.completions.create.call_count == 1

def test_get_groq_stats():
    groq_client._request_timestamps = [time.time()] * 5
    original_limit = settings.GROQ_RATE_LIMIT
    settings.GROQ_RATE_LIMIT = 10
    
    try:
        stats = groq_client.get_groq_stats()
        
        assert stats["requests_in_last_minute"] == 5
        assert stats["remaining_requests"] == 5
        assert stats["rate_limit"] == 10
    finally:
        settings.GROQ_RATE_LIMIT = original_limit

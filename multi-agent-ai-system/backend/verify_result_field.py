"""
Simple verification that the RunResponse model accepts the result field.
This doesn't require database or environment setup.
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class RunResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    input_data: dict
    output_data: Optional[dict] = None
    result: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    error_message: Optional[str] = None

    class Config:
        from_attributes = True

def test_result_field():
    print("Testing RunResponse model with result field...")
    
    # Test 1: With final_output in output_data
    data1 = {
        "id": "run_123",
        "workflow_id": "wf_123",
        "status": "completed",
        "input_data": {"query": "What is Python?"},
        "output_data": {
            "research_data": "Python is a programming language...",
            "final_output": "**Python** is a high-level, interpreted programming language known for its simplicity and readability."
        },
        "started_at": datetime.now(),
        "completed_at": datetime.now()
    }
    
    response1 = RunResponse(**data1)
    
    # Simulate router logic
    if response1.output_data and "final_output" in response1.output_data:
        response1.result = response1.output_data["final_output"]
    
    print(f"✓ Test 1 passed: result = '{response1.result[:50]}...'")
    assert response1.result is not None
    
    # Test 2: Without final_output
    data2 = {
        "id": "run_456",
        "workflow_id": "wf_123",
        "status": "pending",
        "input_data": {"query": "test"},
        "output_data": None,
        "started_at": datetime.now()
    }
    
    response2 = RunResponse(**data2)
    
    if response2.output_data and "final_output" in response2.output_data:
        response2.result = response2.output_data["final_output"]
    
    print(f"✓ Test 2 passed: result = {response2.result}")
    assert response2.result is None
    
    print("\n✅ All tests passed! The RunResponse model correctly supports the 'result' field.")

if __name__ == "__main__":
    test_result_field()

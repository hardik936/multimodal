import sys
import os
from datetime import datetime

# Add the parent directory to sys.path to resolve app imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.routers.runs import RunResponse

def test_run_response_result_field():
    print("Testing RunResponse model...")
    
    # Test case 1: output_data has final_output
    mock_run_data_1 = {
        "id": "run_123",
        "workflow_id": "wf_123",
        "status": "completed",
        "input_data": {"query": "test"},
        "output_data": {
            "research_data": "some research",
            "final_output": "This is the clean result."
        },
        "started_at": datetime.now(),
        "completed_at": datetime.now()
    }
    
    # Simulate the logic in the router where we manually populate the result field
    # Because RunResponse is a Pydantic model, we can instantiate it, 
    # BUT the router logic modifies the object *after* ORM fetch.
    # So we should test if the Pydantic model *accepts* the result field.
    
    res1 = RunResponse(**mock_run_data_1)
    
    # Manually populate like the router does
    if mock_run_data_1["output_data"] and "final_output" in mock_run_data_1["output_data"]:
        res1.result = mock_run_data_1["output_data"]["final_output"]
        
    print(f"Test 1 (Has final_output): Result = '{res1.result}'")
    assert res1.result == "This is the clean result."
    
    # Test case 2: output_data missing final_output
    mock_run_data_2 = {
        "id": "run_456",
        "workflow_id": "wf_123",
        "status": "completed",
        "input_data": {"query": "test"},
        "output_data": {
            "research_data": "some research"
        },
        "started_at": datetime.now(),
        "completed_at": datetime.now()
    }
    
    res2 = RunResponse(**mock_run_data_2)
    
    # Manually populate like the router does
    if mock_run_data_2["output_data"] and "final_output" in mock_run_data_2["output_data"]:
        res2.result = mock_run_data_2["output_data"]["final_output"]

    print(f"Test 2 (No final_output): Result = '{res2.result}'")
    assert res2.result is None

    print("All tests passed!")

if __name__ == "__main__":
    try:
        test_run_response_result_field()
    except Exception as e:
        print(f"Test FAILED: {e}")
        sys.exit(1)

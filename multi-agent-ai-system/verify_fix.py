import requests
import time
import sys

API_URL = "http://localhost:8000/api/v1/workflows"

def run_test():
    print("Submitting test workflow...")
    try:
        response = requests.post(API_URL, json={
            "query": "Calculate the square root of 144",
            "mode": "research_only"  # fast mode
        })
        response.raise_for_status()
        data = response.json()
        run_id = data["id"]
        print(f"Workflow submitted. ID: {run_id}")
    except Exception as e:
        print(f"Failed to submit workflow: {e}")
        return

    # Poll for status
    print("Polling for status...")
    for _ in range(30): # Wait up to 30 seconds
        try:
            r = requests.get(f"{API_URL}/{run_id}")
            r.raise_for_status()
            status = r.json()["status"]
            print(f"Status: {status}")
            
            if status in ["completed", "failed"]:
                print(f"Final Status: {status}")
                return
            
            time.sleep(1)
        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(1)
            
    print("Timed out waiting for workflow completion.")

if __name__ == "__main__":
    run_test()

import urllib.request
import json
import time
import sys

def test_workflow():
    url = "http://localhost:8000/api/v1/workflows/multi-agent/run"
    payload = {
        "input": "Create a python script to calculate fibonacci sequence",
        "language": "python",
        "mode": "full"
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    
    print(f"Sending request to {url}...")
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            print("Response received:")
            # print(json.dumps(result, indent=2)) # Output might be large
            
            # Verify keys exist
            expected_keys = ["research_data", "plan_data", "execution_data", "code_data"]
            missing_keys = []
            for key in expected_keys:
                if key in result:
                    print(f"Key '{key}' found.")
                else:
                    print(f"Key '{key}' MISSING.")
                    missing_keys.append(key)
            
            if not missing_keys:
                print("SUCCESS: All keys found.")
            else:
                print("FAILURE: Missing keys.")
                sys.exit(1)
                
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Retry a few times to allow server to start
    max_retries = 5
    for i in range(max_retries):
        try:
            test_workflow()
            break
        except Exception:
            if i < max_retries - 1:
                print("Connection failed, retrying in 2 seconds...")
                time.sleep(2)
            else:
                print("Failed to connect after retries.")
                sys.exit(1)

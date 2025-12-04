"""
Test workflow execution with the new llama-3.3-70b-versatile model
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

print("=" * 80)
print("TESTING WORKFLOW EXECUTION WITH NEW MODEL")
print("=" * 80)

# Get available workflows
print("\n1. Fetching available workflows...")
response = requests.get(f"{BASE_URL}/workflows")
if response.status_code == 200:
    workflows = response.json()
    print(f"✅ Found {len(workflows)} workflow(s)")
    if workflows:
        workflow_id = workflows[0]['id']
        print(f"   Using workflow: {workflows[0]['name']} (ID: {workflow_id})")
else:
    print(f"❌ Failed to fetch workflows: {response.status_code}")
    exit(1)

# Create a test run
print("\n2. Creating a test workflow run...")
run_data = {
    "workflow_id": workflow_id,
    "input_data": {
        "input": "Write a simple hello world function in Python",
        "language": "python",
        "mode": "plan_only"
    }
}

response = requests.post(f"{BASE_URL}/runs", json=run_data)
if response.status_code == 201:
    run = response.json()
    run_id = run['id']
    print(f"✅ Created run ID: {run_id}")
    print(f"   Status: {run['status']}")
else:
    print(f"❌ Failed to create run: {response.status_code}")
    print(f"   Response: {response.text}")
    exit(1)

# Execute the run
print("\n3. Executing workflow run...")
response = requests.post(f"{BASE_URL}/runs/{run_id}/execute")
if response.status_code == 200:
    print("✅ Workflow execution started")
else:
    print(f"❌ Failed to execute: {response.status_code}")
    print(f"   Response: {response.text}")
    exit(1)

# Monitor progress
print("\n4. Monitoring execution progress...")
max_attempts = 30
for i in range(max_attempts):
    time.sleep(2)
    response = requests.get(f"{BASE_URL}/runs/{run_id}")
    if response.status_code == 200:
        run = response.json()
        status = run['status']
        print(f"   [{i+1}/{max_attempts}] Status: {status}")
        
        if status == 'completed':
            print("\n✅ Workflow completed successfully!")
            print(f"\nOutput Data:")
            print(json.dumps(run.get('output_data', {}), indent=2))
            break
        elif status == 'failed':
            print("\n❌ Workflow failed!")
            print(f"Error: {run.get('error_message', 'Unknown error')}")
            break
    else:
        print(f"❌ Failed to get run status: {response.status_code}")
        break
else:
    print("\n⏱️ Timeout: Workflow is still running after 60 seconds")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)

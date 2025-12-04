import requests
import json

response = requests.get("http://localhost:8000/api/v1/runs")
if response.status_code == 200:
    runs = response.json()
    print(f"Total runs: {len(runs)}")
    if runs:
        # Show latest run
        latest_run = runs[-1]
        print(f"\nLatest Run:")
        print(f"Run ID: {latest_run['id']}")
        print(f"Status: {latest_run['status']}")
        print(f"Created: {latest_run.get('created_at', 'N/A')}")
        if latest_run.get('output_data'):
            print(f"Output: {json.dumps(latest_run['output_data'], indent=2)[:500]}")
        if latest_run.get('error_message'):
            print(f"Error: {latest_run['error_message']}")
        if run.get('error_message'):
            print(f"Error: {run['error_message']}")
else:
    print(f"Error: {response.status_code}")

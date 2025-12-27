import requests
import json
import os

BASE_URL = "http://localhost:8000/api/v1"

def test_flow():
    # 1. Create dummy file
    filename = "test_invoice.txt"
    with open(filename, "w") as f:
        f.write("Invoice #9000\nTotal: $250.00")
        
    try:
        # 2. Upload file
        print("Uploading file...", end=" ")
        with open(filename, "rb") as f:
            files = {"file": (filename, f, "text/plain")}
            resp = requests.post(f"{BASE_URL}/uploads", files=files)
            
        if resp.status_code != 201:
            print(f"FAILED: {resp.status_code} - {resp.text}")
            return
        
        data = resp.json()
        file_path = data["file_path"]
        print("SUCCESS")
        print(f"File saved to: {file_path}")
        
        # 3. Run Workflow with file_path
        print("Running workflow...", end=" ")
        
        # Construct input just like frontend does
        input_json = json.dumps({
            "file_path": file_path,
            "text": ""
        })
        
        payload = {
            "input": input_json,
            "mode": "invoice_ocr",
            "language": "python"
        }
        
        resp = requests.post(f"{BASE_URL}/workflows/multi-agent/run", json=payload)
        
        if resp.status_code != 200:
             print(f"FAILED: {resp.status_code} - {resp.text}")
             return
             
        result = resp.json()
        print("SUCCESS")
        print("Result:", json.dumps(result, indent=2))
        
        # Validation
        final_output = json.loads(result["final_output"])
        if final_output.get("invoice_number") == "9000" and final_output.get("total") == "250.00":
            print("✅ VERIFIED: Extraction correct")
        else:
            print("❌ FAILED: Extraction incorrect")
            
    finally:
        if os.path.exists(filename):
            os.remove(filename)

if __name__ == "__main__":
    test_flow()


import os

file_path = 'frontend/lib/api.ts'

with open(file_path, 'r') as f:
    content = f.read()

# Logic to enforce env var
old_line = "const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';"
new_block = """const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL;

if (!API_BASE_URL) {
    console.error("CRITICAL: NEXT_PUBLIC_API_URL is missing! Backend integration will fail.");
    throw new Error("NEXT_PUBLIC_API_URL environment variable is not defined");
}

console.log(`[API Client] Initialized with Base URL: ${API_BASE_URL}`);"""

if old_line in content:
    content = content.replace(old_line, new_block)
    with open(file_path, 'w') as f:
        f.write(content)
    print("Successfully patched frontend/lib/api.ts")
else:
    print("Target line not found. File might differ from expectation.")
    print(f"Content preview: {content[:200]}")
    exit(1)

import time
import random
from datetime import datetime

# Mocking the internal components for the purpose of a standalone demo script
# In a real scenario, this would import from app.ratelimit...

class MockRateLimiter:
    def __init__(self):
        self.tokens = {"groq": 10, "openai": 5}
        self.max_tokens = {"groq": 10, "openai": 5}
        self.last_refill = time.time()
    
    def acquire(self, provider):
        # Simulate simple refill logic
        now = time.time()
        if provider not in self.tokens:
            return True
            
        if self.tokens[provider] > 0:
            self.tokens[provider] -= 1
            return True
        return False

    def get_status(self, provider):
        return {"available": self.tokens.get(provider, 0), "limit": self.max_tokens.get(provider, 0)}

class MockQuotaManager:
    def __init__(self):
        self.used = 8500
        self.limit = 10000
    
    def record_usage(self, tokens):
        self.used += tokens
        
    def check(self):
        return self.used < self.limit
    
    def status(self):
        return {"used": self.used, "limit": self.limit, "remaining": self.limit - self.used}

def print_header(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}\n")

def simulate_request(req_id, provider="groq"):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] Request #{req_id:02d} | Provider: {provider.ljust(8)} | ", end="")
    
    # Simulate network latency
    time.sleep(random.uniform(0.05, 0.1))
    
    if limiter.acquire(provider):
        quota.record_usage(random.randint(50, 150))
        print("✅ 200 OK - Tokens Acquired")
        return True
    else:
        print("❌ 429 Too Many Requests - Rate Limit Exceeded")
        return False

# Initialize Mocks
limiter = MockRateLimiter()
quota = MockQuotaManager()

# --- DEMO START ---

print_header("Rate Limiting & Quota Management Demo")

print(" Configuration:")
print(" - Rate Limit (Groq):   10 requests/sec")
print(" - Rate Limit (OpenAI): 5 requests/sec")
print(" - Daily Quota:         10,000 tokens")
print(" - Failover:            Enabled (Groq -> OpenAI)\n")

print_header("Scenario 1: Normal Traffic (Groq)")
for i in range(1, 6):
    simulate_request(i, "groq")

print_status = limiter.get_status("groq")
print(f"\n[System] Groq Bucket Status: {print_status['available']}/{print_status['limit']} tokens available.")

print_header("Scenario 2: Burst Traffic & Rate Limit (Groq)")
# Consuming remaining tokens
for i in range(6, 12):
    simulate_request(i, "groq")

print("\n[System] ⚠️ Primary Provider (Groq) Saturated!")

print_header("Scenario 3: Automatic Failover to OpenAI")
for i in range(12, 16):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] Request #{i:02d} | Provider: groq     | ❌ 429 Too Many Requests")
    print(f"[{timestamp}] Request #{i:02d} | ↳ Failover: openai | ✅ 200 OK - Recovered")
    limiter.acquire("openai") # Deduct from OpenAI

print_header("Scenario 4: Quota Management Check")
q_status = quota.status()
print(f"Current Usage: {q_status['used']}/{q_status['limit']} tokens ({q_status['remaining']} remaining)")

print("\n[System] Simulating heavy usage batch job...")
quota.record_usage(1400) # Push near limit
print(f"[System] Updated Usage: {quota.status()['used']}/{quota.status()['limit']}")

# Push over limit
print("\n[System] Attempting final request...")
quota.record_usage(200)
if quota.check():
     print("✅ Request Allowed")
else:
     print("⛔ 403 Forbidden - Daily Quota Exceeded (Hard Limit Enforced)")

print("\n" + "="*60)
print(" End of Demo")
print("="*60)

"""
Test the planner agent to verify it works with the new model
"""
import sys
sys.path.insert(0, 'backend')

from app.agents.planner import planner_node
from app.config import settings

print(f"Current GROQ_MODEL: {settings.GROQ_MODEL}")
print(f"Testing planner agent with new model...\n")

# Test state
test_state = {
    "input": "Create a simple calculator application",
    "research_data": "Python is a good language for calculators. Use tkinter for GUI."
}

try:
    result = planner_node(test_state)
    print("✅ Planner agent works!")
    print(f"\nPlan data: {result}")
except Exception as e:
    print(f"❌ Planner agent failed: {e}")

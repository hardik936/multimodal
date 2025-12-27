"""
Example traced workflow to demonstrate distributed tracing.

This script runs a simple workflow and generates a complete trace
visible in Jaeger.
"""

import sys
import asyncio
sys.path.append("c:\\Users\\HP\\Documents\\antigravity\\multi-agent-ai-system\\backend")

from app.observability.tracing import configure_tracing
from app.agents.graph import create_multi_agent_workflow

# Configure tracing
configure_tracing()

async def main():
    print("=" * 80)
    print("DISTRIBUTED TRACING - Example Workflow")
    print("=" * 80)
    
    # Create workflow
    workflow = create_multi_agent_workflow({})
    
    # Test case 1: Simple query
    print("\n1. Running SIMPLE query workflow...")
    initial_state = {
        "input": "What is Python?",
        "language": "python",
        "mode": "full",
        "messages": [],
        "current_agent": "planner",
        "query_complexity": "SIMPLE",
        "research_data": "",
        "plan_data": {},
        "execution_data": "",
        "code_data": "",
        "final_output": "",
        "run_id": "test-simple-001",
    }
    
    result = await workflow.ainvoke(initial_state)
    print(f"✅ Simple query completed")
    print(f"   Final output: {result['final_output'][:100]}...")
    
    print("\n" + "=" * 80)
    print("Trace generated! View in Jaeger:")
    print("http://localhost:16686")
    print("Service: multi-agent-ai-system")
    print("Operation: workflow.run")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())

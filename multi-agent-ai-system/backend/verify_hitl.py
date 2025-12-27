import sys
import os
import shutil
import asyncio
import sqlite3
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

# Setup path to specific parent directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END

# Import app modules
from app.database import SessionLocal, Base, engine
from app.hitl.models import ReviewDecision, ReviewStatus, ReviewRequest
from app.hitl.queue import ReviewQueueService
from app.hitl.decisions import DecisionService
from app.hitl.gates import DEFAULT_GATES
from app.agents.graph import create_graph, AgentState

# Ensure DB tables exist
Base.metadata.create_all(bind=engine)

# --- MOCKS ---
# We mock the actual node functions to avoid LLM calls
async def mock_research_node(state, *args, **kwargs):
    print("   [Mock] Researcher running...", flush=True)
    return {"research_data": "Mock research"}

async def mock_planner_node(state, *args, **kwargs):
    print("   [Mock] Planner running...", flush=True)
    return {"plan_data": "Mock plan"}

async def mock_executor_node(state, *args, **kwargs):
    print("   [Mock] Executor running...", flush=True)
    return {"execution_data": "Mock execution results"}

async def mock_coder_node(state, *args, **kwargs):
    print("   [Mock] Coder running...", flush=True)
    return {"code_data": "Mock code"}

async def mock_finalizer_node(state, *args, **kwargs):
    print("   [Mock] Finalizer running...", flush=True)
    return {"final_output": "Mock Final Output"}

def mock_should_continue_after_research(state):
    return "planner"

def mock_should_continue_after_plan(state):
    return "executor"

def run_hitl_simulation():
    print(">>> Starting HITL Logic-Level Simulation (Mocked Agents)")

    run_id = f"sim-run-{uuid.uuid4()}"
    thread_id = run_id
    workflow_id = "sim-workflow-001"
    
    # 1. Setup Checkpointer (MemorySaver)
    checkpointer = MemorySaver()
    conn = None # Not needed
    
    # 2. Determine Interrupts
    interrupt_before = ["executor"]
    print(f"1. Configured interrupt_before: {interrupt_before}")
    
    # Context Manager Patches to ensure they are active when create_graph is called
    with patch("app.agents.graph.research_node", new=mock_research_node), \
         patch("app.agents.graph.planner_node", new=mock_planner_node), \
         patch("app.agents.graph.executor_node", new=mock_executor_node), \
         patch("app.agents.graph.coder_node", new=mock_coder_node), \
         patch("app.agents.graph.finalizer_node", new=mock_finalizer_node), \
         patch("app.agents.graph.should_continue_after_research", new=mock_should_continue_after_research), \
         patch("app.agents.graph.should_continue_after_plan", new=mock_should_continue_after_plan):
        
        # Verify Patch
        import app.agents.graph
        print(f"DEBUG: research_node is {app.agents.graph.research_node}", flush=True)
        
        # 3. Create Graph
        workflow = create_graph(checkpointer=checkpointer, interrupt_before=interrupt_before)
        
        # 4. Initial Execution
        print(f"2. Starting execution for run_id: {run_id}")
        initial_state = {
            "input": "Test HITL",
            "language": "en",
            "query_complexity": "COMPLEX", # Force complex path
            "mode": "execution",
            "research_data": None,
            "plan_data": None,
            "messages": [],
            "workflow_id": workflow_id
        }
        thread_config = {"configurable": {"thread_id": thread_id}}
        
        try:
            asyncio.run(workflow.ainvoke(initial_state, thread_config))
        except Exception as e:
            print(f"DEBUG: ainvoke failed with {e}")
            import traceback
            traceback.print_exc()
            
        state_snapshot = workflow.get_state(thread_config)
        print(f"3. Execution halted. Next step: {state_snapshot.next}")
        
        if not state_snapshot.next:
            print(f"❌ Error: Workflow finished unexpectedly. State: {state_snapshot.values}")
            return

        next_step = state_snapshot.next[0]
        if next_step != "executor":
            print(f"❌ Error: Paused at '{next_step}', expected 'executor'.")
            return
            
        print("✅ Verified: Workflow paused at 'executor'.")

        # 5. Create Review Request
        print("4. Creating Review Request via Service...")
        db = SessionLocal()
        review_id = None
        try:
            with ReviewQueueService(db) as queue:
                gate = DEFAULT_GATES.get("executor")
                # Ensure we have a valid gate, if None, create one
                if not gate:
                   from app.hitl.gates import ApprovalGate
                   gate = ApprovalGate(step="executor", risk_level="medium", timeout_minutes=60)

                req = queue.create_review_request(
                    workflow_id=workflow_id,
                    run_id=run_id,
                    thread_id=thread_id,
                    step_name=next_step,
                    gate=gate,
                    snapshot_id=state_snapshot.config['configurable'].get('checkpoint_id'),
                    proposed_action={"description": "Planning complete, ready to execute."}
                )
                review_id = req.id
                print(f"   -> Review Request Created: {review_id}")
        finally:
            db.close()

        # 6. Verify Pending
        db = SessionLocal()
        with ReviewQueueService(db) as queue:
            pending = queue.list_pending_reviews(workflow_id)
            if not any(r.id == review_id for r in pending):
                 print("❌ Error: Request not in pending list.")
                 return
            print("✅ Verified: Request is pending.")
        
        # 7. Approve
        print(f"5. Approving Review {review_id}...")
        with DecisionService(db) as decision_service:
            decision_service.submit_decision(
                review_id=review_id,
                decision=ReviewDecision.APPROVE,
                actor="test-verifier",
                reason="Simulation Approval"
            )
        print("✅ Verified: Request approved.")
        
        # 8. Resume
        print("6. Resuming Execution...")
        try:
            final_result = asyncio.run(workflow.ainvoke(None, thread_config))
            print("   -> Resume invocation complete.")
        except Exception as e:
            print(f"❌ Error during resume: {e}")
            import traceback
            traceback.print_exc()
            return

        # 9. Verify Completion
        if "final_output" in final_result and final_result["final_output"] == "Mock Final Output":
             print("✅ Verified: Workflow completed successfully with mock output.")
             print(">>> HITL Simulation SUCCESS <<<")
        else:
             print(f"❌ Error: Final output mismatch. Result keys: {final_result.keys()}")

if __name__ == "__main__":
    try:
        run_hitl_simulation()
    except Exception:
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if os.path.exists("checkpoints_test.db"):
            try:
                os.remove("checkpoints_test.db")
            except:
                pass

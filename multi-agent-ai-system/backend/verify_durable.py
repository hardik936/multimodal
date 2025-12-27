import asyncio
import uuid
from app.database import init_db, SessionLocal
from app.models.checkpoint import Checkpoint as DBCheckpoint
from app.execution.checkpointer import AsyncPostgresSaver
from app.agents.graph import create_graph
from sqlalchemy import select

async def main():
    print("Initializing DB...")
    init_db()
    
    # Create checkpointer
    checkpointer = AsyncPostgresSaver()
    
    # Create graph
    graph = create_graph(workflow_name="default", checkpointer=checkpointer)
    
    # Generate unique thread_id
    thread_id = str(uuid.uuid4())
    print(f"Running workflow with thread_id: {thread_id}")
    
    inputs = {
        "input": "Calculate 5 + 5",
        "language": "python",
        "mode": "full",
        "query_complexity": "SIMPLE",
        "messages": []
    }
    
    config = {"configurable": {"thread_id": thread_id}}
    
    # Run graph
    print("Invoking graph...")
    result = await graph.ainvoke(inputs, config=config)
    print("Graph execution completed.")
    print("Result:", result.get("final_output"))
    
    # Verify persistence
    print("Verifying checkpoints in DB...")
    with SessionLocal() as db:
        stmt = select(DBCheckpoint).where(DBCheckpoint.thread_id == thread_id)
        checkpoints = db.execute(stmt).scalars().all()
        
        print(f"Found {len(checkpoints)} checkpoints.")
        
        if len(checkpoints) > 0:
            print("✅ Durable execution verified: Checkpoints persisted.")
            # Print latest checkpoint content size
            latest = checkpoints[-1]
            print(f"Latest checkpoint ID: {latest.checkpoint_id}")
        else:
            print("❌ Verification FAILED: No checkpoints found.")
            exit(1)

if __name__ == "__main__":
    asyncio.run(main())

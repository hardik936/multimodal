import sys
from app.hitl.queue import ReviewQueueService
from app.hitl.decisions import DecisionService
from app.hitl.models import ReviewDecision, ReviewStatus

def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")

def cmd_list(workflow_id: str = None):
    print_header("Pending Approval Requests")
    with ReviewQueueService() as service:
        reviews = service.list_pending_reviews(workflow_id)
        if not reviews:
            print("No pending reviews found.")
            return

        print(f"{'ID':<38} | {'Workflow':<20} | {'Step':<10} | {'Risk':<6} | {'Created At'}")
        print("-" * 100)
        for r in reviews:
            created = r.created_at.strftime("%Y-%m-%d %H:%M")
            print(f"{r.id:<38} | {r.workflow_id[:18]:<20} | {r.step_name:<10} | {r.risk_level:<6} | {created}")
        print("-" * 100)
        print(f"Total: {len(reviews)} pending requests.")

def cmd_show(review_id: str):
    with ReviewQueueService() as service:
        r = service.get_review(review_id)
        if not r:
            print(f"Error: Review {review_id} not found.")
            return

        print_header(f"Review Details: {review_id}")
        print(f"Workflow ID:   {r.workflow_id}")
        print(f"Run ID:        {r.run_id}")
        print(f"Step Name:     {r.step_name}")
        print(f"Risk Level:    {r.risk_level}")
        print(f"Status:        {r.status.value}")
        print(f"Created At:    {r.created_at}")
        print(f"Expires At:    {r.expires_at}")
        print(f"Checkpoint ID: {r.checkpoint_id}")
        print("-" * 60)
        print("Proposed Action / Context:")
        print(r.proposed_action or "(No context provided)")
        print("-" * 60)

def cmd_approve(review_id: str, actor: str = "cli_admin", reason: str = "Approved via CLI"):
    with DecisionService() as service:
        try:
            req = service.submit_decision(review_id, ReviewDecision.APPROVE, actor, reason)
            print(f"✅ Review {review_id} APPROVED.")
            print("Triggering workflow resumption...")
            
            # Trigger resumption task
            # We import here to avoid circular dependencies if any (though huey task imports agents)
            from app.tasks.huey_tasks import resume_workflow_task
            
            task = resume_workflow_task(req.run_id)
            print(f"Resume task enqueued. Task ID: {task.id}")
            
        except ValueError as e:
            print(f"Error: {e}")

def cmd_reject(review_id: str, actor: str = "cli_admin", reason: str = "Rejected via CLI"):
    with DecisionService() as service:
        try:
            req = service.submit_decision(review_id, ReviewDecision.REJECT, actor, reason)
            print(f"❌ Review {review_id} REJECTED.")
            
            # Rejection might involve aborting or fallback. 
            # For now, we don't auto-resume to abort, but we should probably inform the workflow.
            # Ideally `resume_workflow_task` handles rejection by aborting.
            # Let's enqueue it too so it can read the rejection status and finish the run.
            
            from app.tasks.huey_tasks import resume_workflow_task
            task = resume_workflow_task(req.run_id)
            print(f"Resume/Abort task enqueued. Task ID: {task.id}")

        except ValueError as e:
            print(f"Error: {e}")

def handle_hitl_command():
    if len(sys.argv) < 3:
        print("Usage: python manage.py hitl <command> [args]")
        print("\nCommands:")
        print("  list [workflow_id]         - List pending reviews")
        print("  show <review_id>           - Show review details")
        print("  approve <review_id> [note] - Approve a request")
        print("  reject <review_id> [note]  - Reject a request")
        sys.exit(1)

    command = sys.argv[2]
    
    if command == "list":
        wf_id = sys.argv[3] if len(sys.argv) > 3 else None
        cmd_list(wf_id)
    elif command == "show":
        if len(sys.argv) < 4:
            print("Error: review_id required")
            sys.exit(1)
        cmd_show(sys.argv[3])
    elif command == "approve":
        if len(sys.argv) < 4:
            print("Error: review_id required")
            sys.exit(1)
        reason = sys.argv[4] if len(sys.argv) > 4 else "Approved via CLI"
        cmd_approve(sys.argv[3], reason=reason)
    elif command == "reject":
        if len(sys.argv) < 4:
            print("Error: review_id required")
            sys.exit(1)
        reason = sys.argv[4] if len(sys.argv) > 4 else "Rejected via CLI"
        cmd_reject(sys.argv[3], reason=reason)
    else:
        print(f"Unknown command: {command}")

from typing import Dict, Tuple
from app.database import SessionLocal
from app.eval.store import EvaluationRun, EvaluationResult

def generate_report(run_id: int) -> Tuple[Dict, str]:
    """
    Generates a structured dictionary and a markdown string report for a given run.
    """
    db = SessionLocal()
    try:
        run = db.query(EvaluationRun).get(run_id)
        if not run:
            return {}, f"Run {run_id} not found."
            
        results = db.query(EvaluationResult).filter(EvaluationResult.run_id == run_id).all()
        
        # Summary
        summary = {
            "run_id": run.id,
            "workflow": run.workflow_id,
            "version": run.candidate_version,
            "passed": run.passed,
            "score": run.aggregated_score,
            "total_cost": run.total_cost_usd,
            "start": str(run.start_ts),
            "cases_total": len(results),
            "cases_passed": sum(1 for r in results if r.score >= (1.0 if "exact" in r.reason else 0.8)) # Rough heuristic
        }
        
        # Markdown Builder
        md = f"# Evaluation Report: Run {run.id}\n\n"
        md += f"**Workflow:** `{run.workflow_id}` | **Version:** `{run.candidate_version}`\n\n"
        md += f"**Status:** {'✅ PASSED' if run.passed else '❌ FAILED'}\n"
        md += f"**Score:** {run.aggregated_score:.2f} / 1.0\n"
        md += f"**Total Cost:** ${run.total_cost_usd:.6f}\n\n"
        
        md += "## Case Details\n\n"
        md += "| Case ID | Score | Status | Latency (ms) | Cost ($) | Matcher |\n"
        md += "|---------|-------|--------|--------------|----------|---------|\n"
        
        for r in results:
            status_icon = "✅" if r.score >= (0.8 if "semantic" in r.reason or "context" in r.reason else 1.0) else "❌"
            latency = r.metrics.get("latency_ms", 0)
            cost = r.metrics.get("cost_usd", 0.0)
            matcher = r.reason.replace("Matcher: ", "")
            md += f"| {r.case_id} | {r.score:.2f} | {status_icon} | {latency:.0f} | {cost:.5f} | {matcher} |\n"
            
        return summary, md
    finally:
        db.close()

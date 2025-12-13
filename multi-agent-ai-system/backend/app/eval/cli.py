import typer
import asyncio
import os
from datetime import datetime
from typing import Optional

from app.eval.runner import run_evalset
from app.eval.reporting import generate_report
from app.database import SessionLocal
from app.eval.store import EvaluationRun

app = typer.Typer(help="Automated Evaluation Harness CLI")

@app.command()
def run(
    evalset: str = typer.Option(..., help="Path to evalset YAML file"),
    workflow: str = typer.Option("custom", help="Workflow version tag"),
    concurrency: int = 4
):
    """
    Run an evaluation suite against a workflow version.
    """
    if not os.path.exists(evalset):
        typer.echo(f"Error: File {evalset} not found.")
        raise typer.Exit(code=1)
        
    typer.echo(f"🚀 Starting evaluation using {evalset}...")
    start = datetime.now()
    
    # Run async loop
    try:
        run_id = asyncio.run(run_evalset(evalset, workflow, concurrency))
    except Exception as e:
        typer.echo(f"❌ Execution failed: {e}")
        raise typer.Exit(code=1)
        
    duration = datetime.now() - start
    typer.echo(f"✅ Completed in {duration}. Run ID: {run_id}")
    
    # Show instant report
    summary, md = generate_report(run_id)
    typer.echo("\n" + md)
    
    # Save Report to file
    report_path = f"storage/evaluations/report_{run_id}.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)
    typer.echo(f"\n📄 Report saved to {report_path}")

    if not summary.get("passed"):
        typer.echo("\n❌ Evaluation FAILED (Score below threshold)")
        raise typer.Exit(code=1)

@app.command("list-runs")
def list_runs(workflow: Optional[str] = None, limit: int = 10):
    """
    List past evaluation runs.
    """
    db = SessionLocal()
    try:
        query = db.query(EvaluationRun).order_by(EvaluationRun.start_ts.desc())
        if workflow:
            query = query.filter(EvaluationRun.workflow_id == workflow)
            
        runs = query.limit(limit).all()
        
        typer.echo(f"{'ID':<5} | {'Date':<20} | {'Workflow':<15} | {'Version':<10} | {'Score':<5} | {'Pass'}")
        typer.echo("-" * 80)
        
        for r in runs:
            start_str = r.start_ts.strftime("%Y-%m-%d %H:%M")
            score = f"{r.aggregated_score:.2f}" if r.aggregated_score is not None else "N/A"
            passed = "✅" if r.passed else "❌"
            typer.echo(f"{r.id:<5} | {start_str:<20} | {r.workflow_id:<15} | {r.candidate_version:<10} | {score:<5} | {passed}")
            
    finally:
        db.close()

@app.command("show-run")
def show_run(run_id: int):
    """
    Show detailed report for a specific run.
    """
    summary, md = generate_report(run_id)
    if not summary:
        typer.echo("Run not found.")
        return
        
    typer.echo(md)

if __name__ == "__main__":
    app()

# Automated Evaluation Harness

The Evaluation Harness enables regression testing, benchmarks, and pre-deploy validation of workflow versions.

## 🚀 Quick Start

### 1. Run an EvalSet
```bash
# Run the smoke test against the current codebase
python -m app.eval.cli run --evalset examples/evalsets/general_agent/smoke.yaml
```

### 2. List Past Runs
```bash
python -m app.eval.cli list-runs
```

### 3. Show Details
```bash
python -m app.eval.cli show-run --run-id 1
```

## 📝 Creating EvalSets
EvalSets are YAML files defining a list of test cases.

```yaml
name: my_eval_suite
workflow: my_workflow
cases:
  - id: case_001
    input:
      input: "Why is the sky blue?"
      mode: "research_only"
    expected: "scattering"
    matcher: contains
```

### Matchers
- **exact**: Strict string equality.
- **contains**: Substring search.
- **regex**: Python regex search.
- **json_key**: Verifies keys and values in a JSON object/dict.
- **semantic**: Normalized token overlap (Jaccard similarity).

## 🛡️ Deployment Gating
The deployment system now supports automatic evaluation checks.

If you call `deploy_version(..., evalset_path="path/to/eval.yaml", require_eval_pass=True)`, the system will:
1. Snapshot the code.
2. Run the full evaluation suite.
3. If the score is below threshold (default < 0.85 aggregated), the deployment is **REJECTED**.

## 📊 Reporting
Reports are generated in Markdown format and saved to `storage/evaluations/`.
They include:
- Pass/Fail status
- Aggregated Score
- Cost ($)
- Per-case latency and trace IDs

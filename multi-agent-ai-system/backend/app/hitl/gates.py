from dataclasses import dataclass
from typing import Optional, Literal

@dataclass
class ApprovalGate:
    step: str # The graph node name (e.g., "executor", "human_review")
    risk_level: Literal["low", "medium", "high"] = "medium"
    timeout_seconds: int = 3600 # 1 hour default
    on_reject: Literal["abort", "fallback"] = "abort"
    on_timeout: Literal["reject", "approve"] = "reject"
    description: Optional[str] = None

# Global configuration of gates (could be moved to DB dynamically later)
# For v1, we define them statically or via config
DEFAULT_GATES = {
    "executor": ApprovalGate(
        step="executor",
        risk_level="high",
        description="Review execution plan before running tools."
    ),
    "coder": ApprovalGate(
        step="coder",
        risk_level="medium",
        description="Review code modifications before finalizing."
    )
}

def get_gate_for_step(step_name: str) -> Optional[ApprovalGate]:
    return DEFAULT_GATES.get(step_name)

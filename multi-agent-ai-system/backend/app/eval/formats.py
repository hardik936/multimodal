from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field

class EvalCase(BaseModel):
    id: str
    description: Optional[str] = None
    input: Dict[str, Any]
    expected: Union[Dict[str, Any], str, List[Any], int, float, bool]
    matcher: str = "exact" # exact, json_key, regex, contains, semantic
    weight: float = 1.0
    tags: List[str] = Field(default_factory=list)
    timeout_seconds: Optional[int] = None

class EvalSet(BaseModel):
    name: str
    description: Optional[str] = None
    workflow: str
    cases: List[EvalCase]

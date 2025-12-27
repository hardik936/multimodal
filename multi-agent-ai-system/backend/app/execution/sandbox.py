from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Optional

class ExecutionResult(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float

class ExecutionService(ABC):
    @abstractmethod
    def execute_code(self, language: str, code: str, timeout: int = 30) -> ExecutionResult:
        """
        Execute code in a sandboxed environment.
        """
        pass

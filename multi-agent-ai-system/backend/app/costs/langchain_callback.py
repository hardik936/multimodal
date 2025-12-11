import logging
from typing import Dict, Any, List, Optional
from uuid import UUID
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from app.costs.tracker import record_llm_usage

logger = logging.getLogger(__name__)

class CostTrackingCallbackHandler(BaseCallbackHandler):
    """
    LangChain callback handler to track token usage and cost.
    Expects metadata to be passed in the config or available in the run context.
    """
    
    def __init__(self, workflow_id: str = None, agent_id: str = None):
        self.workflow_id = workflow_id
        self.agent_id = agent_id

    def on_llm_end(self, response: LLMResult, *, run_id: UUID, parent_run_id: Optional[UUID] = None, **kwargs: Any) -> Any:
        try:
            # Aggregate usage from all generations
            prompt_tokens = 0
            completion_tokens = 0
            model_name = "unknown"
            
            # Check LLMResult llm_output
            if response.llm_output:
                # Groq/OpenAI usually provides 'token_usage' in llm_output
                token_usage = response.llm_output.get("token_usage", {})
                prompt_tokens = token_usage.get("prompt_tokens", 0)
                completion_tokens = token_usage.get("completion_tokens", 0)
                model_name = response.llm_output.get("model_name", model_name)
            
            # If not in llm_output, check generations (some providers put it there)
            if prompt_tokens == 0 and completion_tokens == 0 and response.generations:
                # This is fallback, usually not accurate for aggregated calls but better than 0
                for generation in response.generations[0]:
                     if generation.generation_info:
                         usage = generation.generation_info.get("token_usage", {})
                         prompt_tokens += usage.get("prompt_tokens", 0)
                         completion_tokens += usage.get("completion_tokens", 0)

            record_llm_usage(
                workflow_id=self.workflow_id,
                agent_id=self.agent_id,
                run_id=str(run_id),
                provider="groq", # Assuming Groq for now as per this client
                model=model_name,
                tokens_prompt=prompt_tokens,
                tokens_completion=completion_tokens
            )
        except Exception as e:
            logger.warning(f"CostCallback error: {e}")

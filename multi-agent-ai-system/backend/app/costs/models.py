from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from app.models.base import Base

class CostRecord(Base):
    __tablename__ = "llm_cost_records"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    workflow_id = Column(String, index=True, nullable=True)
    run_id = Column(String, index=True, nullable=True)
    agent_id = Column(String, index=True, nullable=True)
    tool_name = Column(String, nullable=True)
    
    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    
    tokens_prompt = Column(Integer, default=0)
    tokens_completion = Column(Integer, default=0)
    tokens_total = Column(Integer, default=0)
    
    cost_usd = Column(Float, default=0.0)
    
    metadata_json = Column(Text, nullable=True)

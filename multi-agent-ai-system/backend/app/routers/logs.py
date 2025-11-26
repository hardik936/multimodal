from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.log import Log
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class LogResponse(BaseModel):
    id: int
    run_id: str
    level: str
    message: str
    timestamp: datetime

    class Config:
        from_attributes = True

@router.get("", response_model=List[LogResponse])
async def list_logs(db: Session = Depends(get_db)):
    return db.query(Log).all()

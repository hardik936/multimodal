from typing import Any, AsyncIterator, Dict, Optional, Tuple, Sequence

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    SerializerProtocol,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

from app.database import SessionLocal
from app.models.checkpoint import Checkpoint as DBCheckpoint, CheckpointWrite as DBCheckpointWrite

class AsyncPostgresSaver(BaseCheckpointSaver):
    """
    Async implementation of a LangGraph CheckpointSaver using SQLAlchemy.
    """
    def __init__(self, serializer: Optional[SerializerProtocol] = None):
        super().__init__()
        self.serde = serializer or JsonPlusSerializer()

    @asynccontextmanager
    async def _get_session(self) -> AsyncIterator[Session]:
        # Helper to get a session. 
        # Since SessionLocal is sync, we wrap operations in run_in_executor eventually, 
        # OR we just use valid sync calls if we were truly async-db backed.
        # But here we are mixing async worker with sync SQLAlchemy.
        # For true async, we'd need AsyncSession. 
        # For now, we will run the DB ops synchronously in this async method 
        # (which blocks the loop, but it's acceptable for this MVP or we use run_in_executor).
        # Better: run blocking DB calls in executor.
        
        # However, to keep it simple and given worker.py uses run_in_executor for DB calls,
        # we can just use the sync session here effectively.
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """
        Get a checkpoint tuple from the database.
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = config["configurable"].get("checkpoint_id")

        import asyncio
        loop = asyncio.get_running_loop()

        def _get():
            with SessionLocal() as db:
                if checkpoint_id:
                    stmt = select(DBCheckpoint).where(
                        DBCheckpoint.thread_id == thread_id, 
                        DBCheckpoint.checkpoint_id == checkpoint_id
                    )
                else:
                    stmt = select(DBCheckpoint).where(
                        DBCheckpoint.thread_id == thread_id
                    ).order_by(DBCheckpoint.checkpoint_id.desc()).limit(1)
                
                result = db.execute(stmt).scalars().first()
                if not result:
                    return None
                
                # Load writes
                writes_stmt = select(DBCheckpointWrite).where(
                    DBCheckpointWrite.thread_id == thread_id,
                    DBCheckpointWrite.checkpoint_id == result.checkpoint_id
                )
                writes_result = db.execute(writes_stmt).scalars().all()
                
                return result, writes_result

        data = await loop.run_in_executor(None, _get)
        
        if not data:
            return None
        
        db_checkpoint, db_writes = data
        
        checkpoint = self.serde.loads_typed((db_checkpoint.type_, db_checkpoint.checkpoint))
        metadata = self.serde.loads_typed((db_checkpoint.type_, db_checkpoint.metadata_))
        parent_config = (
            {"configurable": {"thread_id": thread_id, "checkpoint_id": db_checkpoint.parent_checkpoint_id}}
            if db_checkpoint.parent_checkpoint_id
            else None
        )
        
        pending_writes = [
            (
                w.task_id,
                w.channel,
                self.serde.loads_typed((w.type_, w.value))
            )
            for w in db_writes
        ]
        
        return CheckpointTuple(
            config={"configurable": {"thread_id": thread_id, "checkpoint_id": db_checkpoint.checkpoint_id}},
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
            pending_writes=pending_writes,
        )

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Dict[str, Any],
    ) -> RunnableConfig:
        """
        Save a checkpoint to the database.
        """
        thread_id = config["configurable"]["thread_id"]
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")
        
        # LangGraph generates the new checkpoint_id (usually uuid or timestamp based)
        # But wait, self.get_next_version? 
        # Actually standard saver implementation:
        
        checkpoint_id = checkpoint["id"]
        
        type_, serialized_checkpoint = self.serde.dumps_typed(checkpoint)
        _, serialized_metadata = self.serde.dumps_typed(metadata)
        
        import asyncio
        loop = asyncio.get_running_loop()

        def _put():
            with SessionLocal() as db:
                db_cp = DBCheckpoint(
                    thread_id=thread_id,
                    checkpoint_id=checkpoint_id,
                    parent_checkpoint_id=parent_checkpoint_id,
                    type_=type_,
                    checkpoint=serialized_checkpoint,
                    metadata_=serialized_metadata
                )
                db.merge(db_cp)
                db.commit()

        await loop.run_in_executor(None, _put)

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """
        Save writes to the database.
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = config["configurable"]["checkpoint_id"]
        
        import asyncio
        loop = asyncio.get_running_loop()

        def _put_writes():
            with SessionLocal() as db:
                for idx, (channel, value) in enumerate(writes):
                    type_, serialized_value = self.serde.dumps_typed(value)
                    
                    # Upsert (merge)
                    db_write = DBCheckpointWrite(
                        thread_id=thread_id,
                        checkpoint_id=checkpoint_id,
                        task_id=task_id,
                        idx=idx,
                        channel=channel,
                        type_=type_,
                        value=serialized_value
                    )
                    db.merge(db_write)
                db.commit()

        await loop.run_in_executor(None, _put_writes)

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from uuid import uuid4

class JobState(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD = "dead"

class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    command: str
    state: JobState = JobState.PENDING
    attempts: int = 0
    max_retries: int = 3
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    next_retry_at: Optional[datetime] = None
    last_error: Optional[str] = None
    run_at: Optional[datetime] = None  # For scheduled jobs (bonus feature)
    priority: int = 0  # For priority queues (bonus feature)
    output: Optional[str] = None  # For job output logging (bonus feature)
    timeout: Optional[int] = None  # For job timeout handling (bonus feature)
import pytest
import tempfile
import os
from datetime import datetime
from src.models.job import Job, JobState
from src.storage.database import Storage
from src.workers.worker import Worker

@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    try:
        os.unlink(db_path)
    except PermissionError:
        pass  # File might still be locked, will be cleaned up later

@pytest.fixture
def storage(temp_db):
    return Storage(temp_db)

def test_job_creation():
    job = Job(command="echo 'test'")
    assert job.state == JobState.PENDING
    assert job.attempts == 0
    assert isinstance(job.created_at, datetime)

def test_storage_add_job(storage):
    job = Job(command="echo test")
    storage.add_job(job.model_dump())
    retrieved = storage.get_job(job.id)
    assert retrieved is not None
    assert retrieved.command == "echo test"
    assert retrieved.state == JobState.PENDING

def test_storage_update_job(storage):
    job = Job(command="echo test")
    storage.add_job(job.model_dump())
    
    storage.update_job(job.id, {"state": JobState.COMPLETED})
    retrieved = storage.get_job(job.id)
    assert retrieved.state == JobState.COMPLETED

def test_worker_process_successful_job(storage):
    # Create a test job
    job = Job(command="echo test")
    storage.add_job(job.model_dump())
    
    # Process the job
    worker = Worker(1, storage)
    worker.process_job(storage.get_job(job.id))
    
    # Verify job completion
    processed_job = storage.get_job(job.id)
    assert processed_job.state == JobState.COMPLETED
    assert processed_job.output == 'test'
    assert processed_job.attempts == 1  # Should be incremented

def test_worker_process_failed_job(storage):
    # Create a test job with an invalid command
    job = Job(command="invalid_command", max_retries=1)
    storage.add_job(job.model_dump())
    
    # Process the job
    worker = Worker(1, storage)
    worker.process_job(storage.get_job(job.id))
    
    # Verify job failure
    processed_job = storage.get_job(job.id)
    assert processed_job.state == JobState.DEAD  # Should be dead after max retries
    assert processed_job.attempts == 1  # Should be incremented once
    assert processed_job.last_error is not None
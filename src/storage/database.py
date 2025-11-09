from sqlalchemy import create_engine, Column, String, Integer, DateTime, Enum as SQLEnum
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from datetime import datetime, timezone
from ..models.job import JobState
import json

Base = declarative_base()

class JobModel(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    command = Column(String, nullable=False)
    state = Column(SQLEnum(JobState), nullable=False, default=JobState.PENDING)
    attempts = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    next_retry_at = Column(DateTime, nullable=True)
    last_error = Column(String, nullable=True)
    run_at = Column(DateTime, nullable=True)
    priority = Column(Integer, default=0)
    output = Column(String, nullable=True)
    timeout = Column(Integer, nullable=True)

class Storage:
    def __init__(self, db_path: str = None):
        if not db_path:
            db_path = os.path.join(os.path.expanduser("~"), ".queuecli", "jobs.db")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        self.engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        
    def __del__(self):
        if hasattr(self, 'engine'):
            self.engine.dispose()

    def add_job(self, job_data: dict):
        session = self.Session()
        try:
            job = JobModel(**job_data)
            session.add(job)
            session.commit()
            return job
        finally:
            session.close()

    def get_job(self, job_id: str):
        session = self.Session()
        try:
            return session.query(JobModel).filter(JobModel.id == job_id).first()
        finally:
            session.close()

    def update_job(self, job_id: str, updates: dict):
        session = self.Session()
        try:
            job = session.query(JobModel).filter(JobModel.id == job_id).first()
            if job:
                for key, value in updates.items():
                    setattr(job, key, value)
                session.commit()
                return job
            return None
        finally:
            session.close()

    def list_jobs(self, state: JobState = None, limit: int = None):
        session = self.Session()
        try:
            query = session.query(JobModel)
            if state:
                query = query.filter(JobModel.state == state)
            if limit:
                query = query.limit(limit)
            return query.all()
        finally:
            session.close()

    def get_next_pending_job(self):
        session = self.Session()
        try:
            # Get the next pending job, ordered by priority and creation time
            return (
                session.query(JobModel)
                .filter(JobModel.state == JobState.PENDING)
                .filter((JobModel.run_at.is_(None)) | (JobModel.run_at <= datetime.utcnow()))
                .order_by(JobModel.priority.desc(), JobModel.created_at.asc())
                .first()
            )
        finally:
            session.close()

    def cleanup_stale_jobs(self):
        """Reset any processing jobs that might have been left in a processing state"""
        session = self.Session()
        try:
            stale_jobs = session.query(JobModel).filter(JobModel.state == JobState.PROCESSING)
            for job in stale_jobs:
                if job.attempts >= job.max_retries:
                    job.state = JobState.DEAD
                else:
                    job.state = JobState.FAILED
            session.commit()
        finally:
            session.close()
import subprocess
import threading
import time
import signal
from datetime import datetime, timedelta, timezone
from ..models.job import JobState
from ..storage.database import Storage
import logging
import math
import os

class Worker:
    def __init__(self, worker_id: int, storage: Storage, base_delay: int = 2):
        self.worker_id = worker_id
        self.storage = storage
        self.base_delay = base_delay
        self.running = False
        self._stop_event = threading.Event()
        self.current_job = None
        self.logger = logging.getLogger(f"worker_{worker_id}")

    def start(self):
        self.running = True
        self._stop_event.clear()
        self.run()

    def stop(self):
        self.running = False
        self._stop_event.set()

    def calculate_next_retry(self, attempts: int) -> datetime:
        """Calculate next retry time using exponential backoff"""
        delay = math.pow(self.base_delay, attempts)
        return datetime.now(timezone.utc) + timedelta(seconds=delay)

    def execute_command(self, command: str, timeout: int = None) -> tuple[int, str, str]:
        """Execute a shell command and return exit code, stdout, and stderr"""
        try:
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                return process.returncode, stdout, stderr
            except subprocess.TimeoutExpired:
                process.kill()
                return -1, "", "Job timed out"
                
        except Exception as e:
            return -1, "", str(e)

    def process_job(self, job):
        """Process a single job"""
        if not job:
            return

        self.current_job = job
        exit_code = -1
        stdout = ""
        stderr = ""

        try:
            # Update job state to processing
            self.storage.update_job(job.id, {
                "state": JobState.PROCESSING,
                "attempts": job.attempts + 1,  # Increment attempts at the start
                "updated_at": datetime.now(timezone.utc)
            })

            # Execute the command
            exit_code, stdout, stderr = self.execute_command(job.command, job.timeout)

            if exit_code == 0:
                # Job completed successfully
                self.storage.update_job(job.id, {
                    "state": JobState.COMPLETED,
                    "output": stdout.strip(),  # Strip whitespace and quotes
                    "updated_at": datetime.now(timezone.utc)
                })
            else:
                # Job failed
                job.attempts += 1
                
                if job.attempts >= job.max_retries:
                    # Move to DLQ
                    self.storage.update_job(job.id, {
                        "state": JobState.DEAD,
                        "last_error": stderr or "Unknown error",
                        "output": stdout,
                        "updated_at": datetime.utcnow()
                    })
                else:
                    # Schedule retry
                    next_retry = self.calculate_next_retry(job.attempts)
                    self.storage.update_job(job.id, {
                        "state": JobState.FAILED,
                        "attempts": job.attempts,
                        "last_error": stderr or "Unknown error",
                        "next_retry_at": next_retry,
                        "output": stdout,
                        "updated_at": datetime.utcnow()
                    })

        except Exception as e:
            self.logger.error(f"Error processing job {job.id}: {str(e)}")
            self.storage.update_job(job.id, {
                "state": JobState.FAILED,
                "last_error": str(e),
                "updated_at": datetime.utcnow()
            })

        finally:
            self.current_job = None

    def run(self):
        """Main worker loop"""
        while self.running:
            try:
                # Get next pending job
                job = self.storage.get_next_pending_job()
                
                if job:
                    self.process_job(job)
                else:
                    # No jobs available, sleep for a short time
                    time.sleep(1)
                    
                # Check if we should stop
                if self._stop_event.is_set():
                    break
                    
            except Exception as e:
                self.logger.error(f"Worker error: {str(e)}")
                time.sleep(1)  # Prevent tight loop on persistent errors

class WorkerManager:
    def __init__(self, storage: Storage):
        self.storage = storage
        self.workers = {}
        self._lock = threading.Lock()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)

    def start_workers(self, count: int = 1):
        """Start the specified number of worker processes"""
        with self._lock:
            for i in range(count):
                worker_id = len(self.workers) + 1
                worker = Worker(worker_id, self.storage)
                thread = threading.Thread(target=worker.start, daemon=True)
                self.workers[worker_id] = (worker, thread)
                thread.start()

    def stop_workers(self):
        """Stop all workers gracefully"""
        with self._lock:
            for worker, thread in self.workers.values():
                worker.stop()
            
            # Wait for all workers to finish their current jobs
            for worker, thread in self.workers.values():
                thread.join()
            
            self.workers.clear()

    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print("\nShutting down workers gracefully...")
        self.stop_workers()
        os._exit(0)  # Exit after cleanup

    def get_active_workers_count(self):
        """Get the count of currently active workers"""
        return len(self.workers)
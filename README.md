# QueueCTL

QueueCTL is a CLI-based background job queue system that manages background jobs with worker processes, handles retries using exponential backoff, and maintains a Dead Letter Queue (DLQ) for permanently failed jobs.

## Features

- ✅ Job enqueuing and management
- ✅ Multiple worker process support
- ✅ Automatic retries with exponential backoff
- ✅ Dead Letter Queue (DLQ) for failed jobs
- ✅ Persistent job storage using SQLite
- ✅ Configurable retry and backoff settings
- ✅ Clean CLI interface with help texts
- ✅ Job priority support
- ✅ Scheduled/delayed jobs support
- ✅ Job output logging
- ✅ Job timeout handling

## Setup Instructions

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/queuectl.git
   cd queuectl
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage Examples

### Enqueuing a Job

```bash
python queuectl.py enqueue '{"command": "echo \"Hello World\"", "max_retries": 3}'
```

### Starting Workers

```bash
# Start 3 worker processes
python queuectl.py worker start --count 3
```

### Checking Queue Status

```bash
python queuectl.py status
```

### Listing Jobs

```bash
# List all pending jobs
python queuectl.py list --state pending

# List all jobs in DLQ
python queuectl.py dlq list
```

### Managing Dead Letter Queue

```bash
# List jobs in DLQ
python queuectl.py dlq list

# Retry a job from DLQ
python queuectl.py dlq retry <job-id>
```

### Configuration Management

```bash
# Set maximum retry attempts
python queuectl.py config set max-retries 5

# Set backoff base (for exponential backoff)
python queuectl.py config set backoff-base 2
```

## Architecture Overview

### Job Lifecycle

1. Jobs start in the `pending` state
2. Workers pick up jobs and move them to `processing`
3. Successfully completed jobs move to `completed`
4. Failed jobs move to `failed` and are retried with exponential backoff
5. Jobs that exceed max retries move to the Dead Letter Queue (`dead` state)

### Data Persistence

- Uses SQLite database for job storage
- Database file located at `~/.queuectl/jobs.db`
- Configuration stored in `~/.queuectl/config.json`

### Worker Process Logic

1. Workers run in separate threads for parallel processing
2. Each worker:
   - Picks up the next available job
   - Executes the command in a subprocess
   - Handles success/failure based on exit code
   - Implements exponential backoff for retries
   - Manages job timeouts

## Testing

Run the test suite:

```bash
pytest tests/
```

### Test Scenarios

1. Basic job execution:
   ```bash
   python queuectl.py enqueue '{"command": "echo \"Success\""}' 
   python queuectl.py worker start
   ```

2. Failed job with retries:
   ```bash
   python queuectl.py enqueue '{"command": "invalid_command"}'
   python queuectl.py worker start
   ```

3. Multiple workers:
   ```bash
   python queuectl.py worker start --count 3
   python queuectl.py status  # Check worker count
   ```

## Assumptions & Trade-offs

1. **SQLite Database**
   - Pros: Simple, embedded, no external dependencies
   - Cons: Limited concurrency, not suitable for distributed setups

2. **Thread-based Workers**
   - Pros: Simple to implement, share memory
   - Cons: Limited by Python's GIL, not truly parallel

3. **File-based Locking**
   - Pros: Simple implementation
   - Cons: May have edge cases in network filesystems

4. **In-Process Queue Management**
   - Pros: Simple, low latency
   - Cons: No cross-process communication

## Future Improvements

1. Redis/message broker backend option
2. Web dashboard for monitoring
3. Job dependencies and workflows
4. Better error reporting and logging
5. Distributed worker support
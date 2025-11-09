import click
import json
from datetime import datetime
import os
from rich.console import Console
from rich.table import Table
from ..storage.database import Storage
from ..workers.worker import WorkerManager
from ..models.job import Job, JobState

console = Console()
storage = Storage()
worker_manager = WorkerManager(storage)

@click.group()
def cli():
    """QueueCLI - A CLI-based background job queue system"""
    pass

@cli.command()
@click.argument('job_json')
def enqueue(job_json):
    """Add a new job to the queue"""
    try:
        job_data = json.loads(job_json)
        if not isinstance(job_data, dict):
            raise ValueError("Job data must be a JSON object")
        
        job = Job(**job_data)
        storage.add_job(job.dict())
        console.print(f"[green]Job {job.id} enqueued successfully[/green]")
        
    except Exception as e:
        console.print(f"[red]Error enqueueing job: {str(e)}[/red]")

@cli.group()
def worker():
    """Manage worker processes"""
    pass

@worker.command('start')
@click.option('--count', default=1, help='Number of workers to start')
def worker_start(count):
    """Start one or more workers"""
    try:
        worker_manager.start_workers(count)
        console.print(f"[green]Started {count} worker(s)[/green]")
    except Exception as e:
        console.print(f"[red]Error starting workers: {str(e)}[/red]")

@worker.command('stop')
def worker_stop():
    """Stop all running workers gracefully"""
    try:
        worker_manager.stop_workers()
        console.print("[green]Workers stopped successfully[/green]")
    except Exception as e:
        console.print(f"[red]Error stopping workers: {str(e)}[/red]")

@cli.command()
def status():
    """Show summary of all job states & active workers"""
    try:
        # Create a table for job states
        table = Table(title="Queue Status")
        table.add_column("State", style="cyan")
        table.add_column("Count", style="magenta")
        
        # Count jobs in each state
        for state in JobState:
            count = len(storage.list_jobs(state=state))
            table.add_row(state.value, str(count))
            
        console.print(table)
        
        # Show active workers
        active_workers = worker_manager.get_active_workers_count()
        console.print(f"\nActive Workers: [green]{active_workers}[/green]")
        
    except Exception as e:
        console.print(f"[red]Error getting status: {str(e)}[/red]")

@cli.command()
@click.option('--state', type=click.Choice(['pending', 'processing', 'completed', 'failed', 'dead']),
              help='Filter jobs by state')
def list(state):
    """List jobs by state"""
    try:
        state_enum = JobState(state) if state else None
        jobs = storage.list_jobs(state=state_enum)
        
        if not jobs:
            console.print("[yellow]No jobs found[/yellow]")
            return
            
        table = Table(title=f"Jobs {f'in {state} state' if state else ''}")
        table.add_column("ID", style="cyan")
        table.add_column("Command", style="magenta")
        table.add_column("State", style="green")
        table.add_column("Attempts", style="yellow")
        table.add_column("Created At", style="blue")
        
        for job in jobs:
            table.add_row(
                job.id,
                job.command[:50] + "..." if len(job.command) > 50 else job.command,
                job.state.value,
                str(job.attempts),
                job.created_at.strftime("%Y-%m-%d %H:%M:%S")
            )
            
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing jobs: {str(e)}[/red]")

@cli.group()
def dlq():
    """Manage Dead Letter Queue"""
    pass

@dlq.command('list')
def dlq_list():
    """List jobs in the Dead Letter Queue"""
    try:
        dead_jobs = storage.list_jobs(state=JobState.DEAD)
        
        if not dead_jobs:
            console.print("[yellow]No jobs in DLQ[/yellow]")
            return
            
        table = Table(title="Dead Letter Queue")
        table.add_column("ID", style="cyan")
        table.add_column("Command", style="magenta")
        table.add_column("Attempts", style="yellow")
        table.add_column("Last Error", style="red")
        
        for job in dead_jobs:
            table.add_row(
                job.id,
                job.command[:50] + "..." if len(job.command) > 50 else job.command,
                str(job.attempts),
                job.last_error[:50] + "..." if job.last_error and len(job.last_error) > 50 else job.last_error or ""
            )
            
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing DLQ: {str(e)}[/red]")

@dlq.command('retry')
@click.argument('job_id')
def dlq_retry(job_id):
    """Retry a job from the Dead Letter Queue"""
    try:
        job = storage.get_job(job_id)
        
        if not job:
            console.print(f"[red]Job {job_id} not found[/red]")
            return
            
        if job.state != JobState.DEAD:
            console.print(f"[yellow]Job {job_id} is not in DLQ (current state: {job.state})[/yellow]")
            return
            
        # Reset job state and attempts
        storage.update_job(job_id, {
            "state": JobState.PENDING,
            "attempts": 0,
            "last_error": None,
            "updated_at": datetime.utcnow()
        })
        
        console.print(f"[green]Job {job_id} moved back to pending queue[/green]")
        
    except Exception as e:
        console.print(f"[red]Error retrying job: {str(e)}[/red]")

@cli.group()
def config():
    """Manage configuration"""
    pass

# Store configuration in ~/.queuecli/config.json
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".queuecli", "config.json")
DEFAULT_CONFIG = {
    "max-retries": 3,
    "backoff-base": 2,
}

def load_config():
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)

@config.command('get')
@click.argument('key')
def config_get(key):
    """Get a configuration value"""
    try:
        config = load_config()
        value = config.get(key)
        if value is None:
            console.print(f"[yellow]Configuration key '{key}' not found[/yellow]")
        else:
            console.print(f"{key}: {value}")
    except Exception as e:
        console.print(f"[red]Error getting configuration: {str(e)}[/red]")

@config.command('set')
@click.argument('key')
@click.argument('value')
def config_set(key, value):
    """Set a configuration value"""
    try:
        config = load_config()
        
        # Convert value to the appropriate type
        try:
            if value.isdigit():
                value = int(value)
            elif value.replace('.', '', 1).isdigit():
                value = float(value)
        except (ValueError, AttributeError):
            pass
            
        config[key] = value
        save_config(config)
        console.print(f"[green]Set {key} to {value}[/green]")
    except Exception as e:
        console.print(f"[red]Error setting configuration: {str(e)}[/red]")

if __name__ == '__main__':
    cli()
"""
Background Task Queue Configuration
Handles asynchronous link enrichment (LLM + embeddings)
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Callable, Any

logger = logging.getLogger(__name__)


# ============================================================================
# TASK QUEUE INTERFACE
# ============================================================================

class TaskQueue(ABC):
    """Abstract base class for task queue implementations"""

    @abstractmethod
    def enqueue(self, func: Callable, *args, **kwargs) -> str:
        """Enqueue a task and return job ID"""
        pass

    @abstractmethod
    def dequeue(self) -> Any:
        """Dequeue next task"""
        pass


# ============================================================================
# IN-MEMORY QUEUE (Development)
# ============================================================================

class InMemoryQueue(TaskQueue):
    """Simple in-memory queue for development (NOT for production)"""

    def __init__(self):
        self.queue = []
        self.jobs = {}

    def enqueue(self, func: Callable, *args, **kwargs) -> str:
        """Add task to queue"""
        import uuid
        job_id = str(uuid.uuid4())

        self.jobs[job_id] = {
            "func": func,
            "args": args,
            "kwargs": kwargs,
            "status": "pending"
        }

        self.queue.append(job_id)
        logger.info(f"Task enqueued: {job_id}")

        return job_id

    def dequeue(self) -> Any:
        """Get next task from queue"""
        if not self.queue:
            return None

        job_id = self.queue.pop(0)
        job = self.jobs[job_id]
        job["status"] = "running"

        return job_id, job


# ============================================================================
# CELERY QUEUE (Production)
# ============================================================================

class CeleryQueue(TaskQueue):
    """Celery task queue for production distributed processing"""

    def __init__(self, broker_url: str = "redis://localhost:6379/0"):
        try:
            from celery import Celery

            self.app = Celery(
                "knowledge_vault",
                broker=broker_url,
                backend=broker_url
            )

            # Configure Celery
            self.app.conf.update(
                task_serializer="json",
                accept_content=["json"],
                result_serializer="json",
                timezone="UTC",
                enable_utc=True,
                task_track_started=True,
                task_time_limit=30 * 60,  # 30 minute hard limit
                task_soft_time_limit=25 * 60,  # 25 minute soft limit
                worker_prefetch_multiplier=1,
                worker_max_tasks_per_child=1000,
            )

            logger.info("Celery queue initialized")

        except ImportError:
            raise RuntimeError(
                "Celery not installed. Install with: pip install celery redis"
            )

    def enqueue(self, func: Callable, *args, **kwargs) -> str:
        """Enqueue task to Celery"""
        task = self.app.send_task(
            func.__name__,
            args=args,
            kwargs=kwargs,
            queue="default"
        )
        logger.info(f"Celery task enqueued: {task.id}")
        return task.id

    def dequeue(self) -> Any:
        """Not used with Celery (workers pull tasks)"""
        pass


# ============================================================================
# QUEUE FACTORY
# ============================================================================

def create_queue() -> TaskQueue:
    """Factory function to create appropriate task queue"""
    environment = os.getenv("ENVIRONMENT", "development")

    if environment == "production":
        broker_url = os.getenv(
            "CELERY_BROKER_URL",
            "redis://localhost:6379/0"
        )
        return CeleryQueue(broker_url)
    else:
        logger.warning("Using in-memory queue (not suitable for production)")
        return InMemoryQueue()


# ============================================================================
# GLOBAL QUEUE INSTANCE
# ============================================================================

background_enrichment_queue = create_queue()


# ============================================================================
# CELERY TASKS (if using Celery)
# ============================================================================

"""
If using Celery, define tasks like this:

from celery import shared_task
from main import background_enrich_link

@shared_task(name="background_enrich_link")
def celery_background_enrich_link(link_id, url, platform, user_id):
    asyncio.run(background_enrich_link(link_id, url, platform, user_id))

Then in main.py, use:
    background_enrichment_queue.app.send_task(
        "background_enrich_link",
        args=(link_id, url, platform, user_id)
    )
"""


# ============================================================================
# REDIS QUEUE (Alternative - RQ)
# ============================================================================

class RQQueue(TaskQueue):
    """Redis Queue (RQ) for production"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        try:
            from rq import Queue
            import redis

            redis_conn = redis.from_url(redis_url)
            self.queue = Queue(connection=redis_conn)
            logger.info("RQ queue initialized")

        except ImportError:
            raise RuntimeError(
                "RQ not installed. Install with: pip install rq redis"
            )

    def enqueue(self, func: Callable, *args, **kwargs) -> str:
        """Enqueue task to RQ"""
        job = self.queue.enqueue(func, *args, **kwargs, job_timeout=1800)
        logger.info(f"RQ job enqueued: {job.id}")
        return job.id

    def dequeue(self) -> Any:
        """Not used with RQ (workers pull tasks)"""
        pass


# ============================================================================
# MONITORING & RETRY LOGIC
# ============================================================================

class TaskRetryPolicy:
    """Retry policy for failed tasks"""

    MAX_RETRIES = 3
    RETRY_DELAY = 60  # seconds
    BACKOFF_FACTOR = 2

    @classmethod
    def should_retry(cls, attempt: int) -> bool:
        """Check if task should be retried"""
        return attempt < cls.MAX_RETRIES

    @classmethod
    def get_retry_delay(cls, attempt: int) -> int:
        """Get retry delay for attempt number"""
        return cls.RETRY_DELAY * (cls.BACKOFF_FACTOR ** attempt)


def enqueue_with_retry(
    queue: TaskQueue,
    func: Callable,
    max_retries: int = 3,
    *args,
    **kwargs
) -> str:
    """
    Enqueue task with automatic retry on failure.

    Args:
        queue: Task queue instance
        func: Function to execute
        max_retries: Maximum retry attempts
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Job ID
    """
    kwargs["max_retries"] = max_retries
    return queue.enqueue(func, *args, **kwargs)


# ============================================================================
# DEVELOPMENT RUNNER (for testing background tasks)
# ============================================================================

async def run_background_queue():
    """
    Run background queue processor (for development).

    In production, use Celery workers or RQ workers instead.
    """
    if not isinstance(background_enrichment_queue, InMemoryQueue):
        logger.info("Using production queue (Celery/RQ). Skipping in-process runner.")
        return

    logger.info("Starting background queue processor...")

    while True:
        job_id, job = background_enrichment_queue.dequeue()

        if not job:
            await asyncio.sleep(1)
            continue

        try:
            logger.info(f"Processing job {job_id}")

            func = job["func"]
            args = job["args"]
            kwargs = job["kwargs"]

            # Execute function
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)

            background_enrichment_queue.jobs[job_id]["status"] = "completed"
            logger.info(f"✓ Job completed: {job_id}")

        except Exception as e:
            logger.error(f"✗ Job failed: {job_id}: {e}")
            background_enrichment_queue.jobs[job_id]["status"] = "failed"
            background_enrichment_queue.jobs[job_id]["error"] = str(e)


# ============================================================================
# MONITORING DASHBOARD (Optional)
# ============================================================================

def get_queue_status() -> dict:
    """Get current queue status"""
    if isinstance(background_enrichment_queue, InMemoryQueue):
        return {
            "queue_type": "in-memory",
            "pending_jobs": len(background_enrichment_queue.queue),
            "total_jobs": len(background_enrichment_queue.jobs),
            "jobs_by_status": {
                "pending": sum(
                    1 for j in background_enrichment_queue.jobs.values()
                    if j["status"] == "pending"
                ),
                "running": sum(
                    1 for j in background_enrichment_queue.jobs.values()
                    if j["status"] == "running"
                ),
                "completed": sum(
                    1 for j in background_enrichment_queue.jobs.values()
                    if j["status"] == "completed"
                ),
                "failed": sum(
                    1 for j in background_enrichment_queue.jobs.values()
                    if j["status"] == "failed"
                ),
            }
        }
    else:
        return {
            "queue_type": "production",
            "status": "running"
        }

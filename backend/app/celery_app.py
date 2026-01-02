"""
Celery configuration for background warmup jobs
"""

import os
from celery import Celery

# Redis URL from environment or default
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Create Celery app
celery_app = Celery(
    "warmup",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks"]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Limits
    task_time_limit=660,  # 11 minutes hard limit
    task_soft_time_limit=600,  # 10 minutes soft limit
    worker_max_tasks_per_child=10,  # Restart worker after 10 tasks (memory cleanup)
    worker_prefetch_multiplier=1,  # One task at a time per worker

    # Retry settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Result expiration
    result_expires=3600,  # 1 hour
)

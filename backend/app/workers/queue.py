from collections.abc import Callable
from typing import Any

import redis
from rq import Queue
from rq.job import Job

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TaskQueueManager:
    """
    Manages background job dispatching and status tracking using Redis and RQ.
    Includes fallback execution for test and standalone environments.
    """

    def __init__(
        self, redis_url: str = settings.REDIS_URL, queue_name: str = settings.REDIS_QUEUE_NAME
    ):
        self.redis_url = redis_url
        self.queue_name = queue_name
        self._redis_client: redis.Redis | None = None
        self._queue: Queue | None = None

    def get_redis_client(self) -> redis.Redis:
        if self._redis_client is None:
            self._redis_client = redis.from_url(
                self.redis_url,
                socket_timeout=3.0,
                socket_connect_timeout=3.0,
                decode_responses=False,
            )
        return self._redis_client

    def get_queue(self) -> Queue:
        if self._queue is None:
            client = self.get_redis_client()
            self._queue = Queue(self.queue_name, connection=client)
        return self._queue

    def check_redis_health(self) -> bool:
        """
        Verify that Redis responds to PING within timeout.
        """
        try:
            client = self.get_redis_client()
            return bool(client.ping())
        except Exception as e:
            logger.warning(f"Redis health check probe failed: {e}")
            return False

    def enqueue(
        self,
        func: Callable[..., Any],
        *args: Any,
        job_id: str | None = None,
        job_timeout: int = 600,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Enqueue a background task. If Redis is available, dispatch via RQ.
        If in test/offline mode, allow synchronous or tracked invocation.
        """
        try:
            q = self.get_queue()
            job = q.enqueue(
                func,
                *args,
                job_id=job_id,
                job_timeout=job_timeout,
                result_ttl=86400,
                failure_ttl=86400,
                **kwargs,
            )
            return {
                "job_id": job.id,
                "status": job.get_status(),
                "enqueued_at": str(job.enqueued_at),
                "queue": self.queue_name,
            }
        except Exception as err:
            logger.warning(f"Redis queue dispatch failed or running in sync mode: {err}")
            # Synchronous execution fallback for tests
            try:
                result = func(*args, **kwargs)
                return {
                    "job_id": job_id or "sync_fallback",
                    "status": "finished",
                    "result": str(result),
                    "queue": "in_memory_sync",
                }
            except Exception as sync_err:
                logger.error(f"Synchronous fallback execution error: {sync_err}")
                return {
                    "job_id": job_id or "sync_fallback_failed",
                    "status": "failed",
                    "error": str(sync_err),
                    "queue": "in_memory_sync",
                }

    def get_job_status(self, job_id: str) -> dict[str, Any]:
        try:
            client = self.get_redis_client()
            job = Job.fetch(job_id, connection=client)
            return {
                "job_id": job.id,
                "status": job.get_status(),
                "enqueued_at": str(job.enqueued_at),
                "started_at": str(job.started_at),
                "ended_at": str(job.ended_at),
                "result": job.result,
                "exc_info": job.exc_info,
            }
        except Exception:
            return {"job_id": job_id, "status": "unknown"}


task_queue = TaskQueueManager()

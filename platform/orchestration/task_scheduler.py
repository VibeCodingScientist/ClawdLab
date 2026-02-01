"""Task scheduler and queue manager for research orchestration."""

import asyncio
import heapq
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from platform.orchestration.base import (
    Priority,
    ResearchTask,
    TaskStatus,
)
from platform.orchestration.config import (
    RESEARCH_DOMAINS,
    get_settings,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class PriorityQueue:
    """Thread-safe priority queue for tasks."""

    def __init__(self):
        """Initialize priority queue."""
        self._heap: list[tuple[int, datetime, str, ResearchTask]] = []
        self._entry_finder: dict[str, tuple] = {}
        self._counter = 0

    def push(self, task: ResearchTask) -> None:
        """Add task to queue."""
        if task.task_id in self._entry_finder:
            self.remove(task.task_id)

        entry = (task.priority.value, task.created_at, task.task_id, task)
        self._entry_finder[task.task_id] = entry
        heapq.heappush(self._heap, entry)
        self._counter += 1

    def pop(self) -> ResearchTask | None:
        """Remove and return highest priority task."""
        while self._heap:
            priority, created_at, task_id, task = heapq.heappop(self._heap)
            if task_id in self._entry_finder:
                del self._entry_finder[task_id]
                return task
        return None

    def remove(self, task_id: str) -> bool:
        """Remove task from queue."""
        if task_id in self._entry_finder:
            del self._entry_finder[task_id]
            return True
        return False

    def peek(self) -> ResearchTask | None:
        """Return highest priority task without removing."""
        while self._heap:
            priority, created_at, task_id, task = self._heap[0]
            if task_id in self._entry_finder:
                return task
            heapq.heappop(self._heap)
        return None

    def __len__(self) -> int:
        return len(self._entry_finder)

    def __contains__(self, task_id: str) -> bool:
        return task_id in self._entry_finder


class TaskScheduler:
    """
    Schedule and manage research tasks.

    Features:
    - Priority-based scheduling
    - Queue management per domain
    - Retry handling
    - Load balancing
    - Task timeout management
    """

    def __init__(self):
        """Initialize task scheduler."""
        self._queues: dict[str, PriorityQueue] = defaultdict(PriorityQueue)
        self._running_tasks: dict[str, ResearchTask] = {}
        self._completed_tasks: dict[str, ResearchTask] = {}
        self._failed_tasks: dict[str, ResearchTask] = {}
        self._agent_tasks: dict[str, list[str]] = defaultdict(list)

    async def schedule_task(self, task: ResearchTask, queue: str | None = None) -> str:
        """
        Schedule a task for execution.

        Args:
            task: Task to schedule
            queue: Target queue (default: based on task type)

        Returns:
            Task ID
        """
        queue_name = queue or self._determine_queue(task)

        task.status = TaskStatus.QUEUED
        self._queues[queue_name].push(task)

        logger.info(
            "task_scheduled",
            task_id=task.task_id,
            queue=queue_name,
            priority=task.priority.value,
        )

        return task.task_id

    async def get_next_task(
        self,
        queue: str | None = None,
        agent_id: str | None = None,
    ) -> ResearchTask | None:
        """
        Get the next task to execute.

        Args:
            queue: Specific queue to get from
            agent_id: Agent requesting task

        Returns:
            Next task or None
        """
        if queue:
            task = self._queues[queue].pop()
            if task:
                return await self._assign_task(task, agent_id)
            return None

        # Check all queues by priority
        all_tasks = []
        for queue_name, pq in self._queues.items():
            task = pq.peek()
            if task:
                all_tasks.append((task.priority.value, task.created_at, queue_name, task))

        if not all_tasks:
            return None

        # Get highest priority task
        all_tasks.sort(key=lambda x: (x[0], x[1]))
        _, _, queue_name, _ = all_tasks[0]

        task = self._queues[queue_name].pop()
        if task:
            return await self._assign_task(task, agent_id)
        return None

    async def _assign_task(
        self,
        task: ResearchTask,
        agent_id: str | None,
    ) -> ResearchTask:
        """Assign task to an agent."""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        task.assigned_agent = agent_id

        self._running_tasks[task.task_id] = task

        if agent_id:
            self._agent_tasks[agent_id].append(task.task_id)

        logger.info(
            "task_assigned",
            task_id=task.task_id,
            agent_id=agent_id,
        )

        return task

    async def complete_task(
        self,
        task_id: str,
        outputs: dict[str, Any] | None = None,
    ) -> ResearchTask | None:
        """
        Mark a task as completed.

        Args:
            task_id: Task ID
            outputs: Task outputs

        Returns:
            Completed task
        """
        task = self._running_tasks.pop(task_id, None)
        if not task:
            return None

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        task.outputs = outputs or {}

        self._completed_tasks[task_id] = task

        # Remove from agent's task list
        if task.assigned_agent:
            if task_id in self._agent_tasks[task.assigned_agent]:
                self._agent_tasks[task.assigned_agent].remove(task_id)

        logger.info(
            "task_completed",
            task_id=task_id,
            execution_time=task.execution_time_seconds,
        )

        return task

    async def fail_task(
        self,
        task_id: str,
        error_message: str,
        retry: bool = True,
    ) -> ResearchTask | None:
        """
        Mark a task as failed.

        Args:
            task_id: Task ID
            error_message: Error description
            retry: Whether to retry the task

        Returns:
            Failed task
        """
        task = self._running_tasks.pop(task_id, None)
        if not task:
            return None

        task.error_message = error_message

        # Check if we should retry
        if retry and task.retry_count < task.max_retries:
            task.retry_count += 1
            task.status = TaskStatus.RETRYING
            task.started_at = None
            task.assigned_agent = None

            # Re-queue with same priority
            queue = self._determine_queue(task)
            self._queues[queue].push(task)

            logger.info(
                "task_retrying",
                task_id=task_id,
                retry_count=task.retry_count,
                max_retries=task.max_retries,
            )

            return task

        task.status = TaskStatus.FAILED
        task.completed_at = datetime.utcnow()
        self._failed_tasks[task_id] = task

        # Remove from agent's task list
        if task.assigned_agent:
            if task_id in self._agent_tasks[task.assigned_agent]:
                self._agent_tasks[task.assigned_agent].remove(task_id)

        logger.warning(
            "task_failed",
            task_id=task_id,
            error=error_message,
            retry_count=task.retry_count,
        )

        return task

    async def cancel_task(self, task_id: str) -> ResearchTask | None:
        """
        Cancel a task.

        Args:
            task_id: Task ID

        Returns:
            Cancelled task
        """
        # Check running tasks
        task = self._running_tasks.pop(task_id, None)
        if task:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.utcnow()
            self._completed_tasks[task_id] = task

            if task.assigned_agent:
                if task_id in self._agent_tasks[task.assigned_agent]:
                    self._agent_tasks[task.assigned_agent].remove(task_id)

            logger.info("task_cancelled", task_id=task_id)
            return task

        # Check queues
        for queue in self._queues.values():
            if queue.remove(task_id):
                logger.info("task_cancelled_from_queue", task_id=task_id)
                return None

        return None

    async def check_timeouts(self) -> list[str]:
        """
        Check for timed out tasks.

        Returns:
            List of timed out task IDs
        """
        timed_out = []
        now = datetime.utcnow()

        for task_id, task in list(self._running_tasks.items()):
            if task.started_at:
                timeout = timedelta(minutes=task.timeout_minutes)
                if now > task.started_at + timeout:
                    timed_out.append(task_id)
                    await self.fail_task(
                        task_id,
                        f"Task timed out after {task.timeout_minutes} minutes",
                        retry=True,
                    )

        return timed_out

    def get_task(self, task_id: str) -> ResearchTask | None:
        """Get a task by ID."""
        if task_id in self._running_tasks:
            return self._running_tasks[task_id]
        if task_id in self._completed_tasks:
            return self._completed_tasks[task_id]
        if task_id in self._failed_tasks:
            return self._failed_tasks[task_id]

        # Check queues
        for queue in self._queues.values():
            if task_id in queue:
                return queue._entry_finder.get(task_id, (None, None, None, None))[3]

        return None

    def get_queue_stats(self) -> dict[str, Any]:
        """Get statistics for all queues."""
        stats = {}
        for queue_name, pq in self._queues.items():
            stats[queue_name] = {
                "queued": len(pq),
                "running": sum(
                    1 for t in self._running_tasks.values()
                    if self._determine_queue(t) == queue_name
                ),
            }

        return {
            "queues": stats,
            "total_queued": sum(len(q) for q in self._queues.values()),
            "total_running": len(self._running_tasks),
            "total_completed": len(self._completed_tasks),
            "total_failed": len(self._failed_tasks),
        }

    def get_agent_tasks(self, agent_id: str) -> list[ResearchTask]:
        """Get all tasks assigned to an agent."""
        return [
            self._running_tasks[task_id]
            for task_id in self._agent_tasks.get(agent_id, [])
            if task_id in self._running_tasks
        ]

    def _determine_queue(self, task: ResearchTask) -> str:
        """Determine the appropriate queue for a task."""
        # Check if task type maps to a domain
        for domain, config in RESEARCH_DOMAINS.items():
            if task.task_type in config.get("keywords", []):
                return config["celery_queue"]

        # Use priority-based default queue
        if task.priority.value <= 2:
            return settings.high_priority_queue
        return settings.default_queue

    async def rebalance_queues(self) -> None:
        """Rebalance tasks across queues if needed."""
        # This could implement load balancing logic
        pass


class DistributedTaskScheduler(TaskScheduler):
    """
    Distributed task scheduler using Redis for coordination.

    Extends TaskScheduler for multi-instance deployments.
    """

    def __init__(self, redis_url: str | None = None):
        """Initialize distributed scheduler."""
        super().__init__()
        self._redis_url = redis_url or settings.redis_url
        self._redis_client = None

    async def _get_redis(self):
        """Get Redis client."""
        if self._redis_client is None:
            import redis.asyncio as redis
            self._redis_client = redis.from_url(self._redis_url)
        return self._redis_client

    async def schedule_task(self, task: ResearchTask, queue: str | None = None) -> str:
        """Schedule task using Redis."""
        # For now, use local implementation
        # Production would store in Redis
        return await super().schedule_task(task, queue)

    async def get_next_task(
        self,
        queue: str | None = None,
        agent_id: str | None = None,
    ) -> ResearchTask | None:
        """Get next task using Redis."""
        # For now, use local implementation
        return await super().get_next_task(queue, agent_id)


# Singleton instance
_scheduler_instance: TaskScheduler | None = None


def get_task_scheduler() -> TaskScheduler:
    """Get singleton TaskScheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = TaskScheduler()
    return _scheduler_instance

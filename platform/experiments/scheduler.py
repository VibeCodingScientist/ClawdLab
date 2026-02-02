"""Resource Estimation and Experiment Scheduling."""

import heapq
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import uuid4

from platform.experiments.base import (
    Experiment,
    ExperimentPlan,
    ExperimentStatus,
    ExperimentStep,
    ResourceEstimate,
    ResourceRequirement,
    ResourceType,
)
from platform.experiments.config import EXPERIMENT_TYPES, RESOURCE_TYPES, get_settings


class ScheduleStatus(Enum):
    """Status of a scheduled item."""

    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ResourcePool:
    """Available resource pool."""

    pool_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    gpu_available: float = 0.0
    cpu_available: float = 0.0
    memory_available_gb: float = 0.0
    storage_available_gb: float = 0.0
    gpu_total: float = 0.0
    cpu_total: float = 0.0
    memory_total_gb: float = 0.0
    storage_total_gb: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "pool_id": self.pool_id,
            "name": self.name,
            "gpu_available": self.gpu_available,
            "cpu_available": self.cpu_available,
            "memory_available_gb": self.memory_available_gb,
            "storage_available_gb": self.storage_available_gb,
            "gpu_total": self.gpu_total,
            "cpu_total": self.cpu_total,
            "memory_total_gb": self.memory_total_gb,
            "storage_total_gb": self.storage_total_gb,
        }

    def utilization(self) -> dict[str, float]:
        """Get resource utilization percentages."""
        return {
            "gpu": (1 - self.gpu_available / max(self.gpu_total, 1)) * 100,
            "cpu": (1 - self.cpu_available / max(self.cpu_total, 1)) * 100,
            "memory": (1 - self.memory_available_gb / max(self.memory_total_gb, 1)) * 100,
            "storage": (1 - self.storage_available_gb / max(self.storage_total_gb, 1)) * 100,
        }


@dataclass
class ScheduledExperiment:
    """A scheduled experiment in the queue."""

    schedule_id: str = field(default_factory=lambda: str(uuid4()))
    experiment_id: str = ""
    experiment: Experiment | None = None
    priority: int = 5
    scheduled_start: datetime | None = None
    estimated_end: datetime | None = None
    status: ScheduleStatus = ScheduleStatus.PENDING
    resource_estimate: ResourceEstimate | None = None
    assigned_pool: str | None = None
    queued_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "experiment_id": self.experiment_id,
            "priority": self.priority,
            "scheduled_start": self.scheduled_start.isoformat() if self.scheduled_start else None,
            "estimated_end": self.estimated_end.isoformat() if self.estimated_end else None,
            "status": self.status.value,
            "resource_estimate": self.resource_estimate.to_dict() if self.resource_estimate else None,
            "assigned_pool": self.assigned_pool,
            "queued_at": self.queued_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def __lt__(self, other: "ScheduledExperiment") -> bool:
        """Compare for priority queue (lower priority value = higher priority)."""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.queued_at < other.queued_at


class ResourceEstimator:
    """Estimates resource requirements for experiments."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._estimation_history: dict[str, ResourceEstimate] = {}
        self._domain_multipliers: dict[str, dict[str, float]] = {
            "ml_ai": {"gpu_hours": 1.5, "cpu_hours": 0.8},
            "mathematics": {"gpu_hours": 0.2, "cpu_hours": 1.5},
            "computational_biology": {"gpu_hours": 1.2, "cpu_hours": 1.3},
            "materials_science": {"gpu_hours": 1.0, "cpu_hours": 1.2},
            "bioinformatics": {"gpu_hours": 0.5, "cpu_hours": 1.8},
        }

    async def estimate_experiment(
        self,
        experiment: Experiment,
        use_history: bool = True,
    ) -> ResourceEstimate:
        """Estimate resources for an experiment."""
        # Get base estimate from experiment type
        base = self._get_base_estimate(experiment.experiment_type)

        # Apply domain multipliers
        domain_mult = self._domain_multipliers.get(experiment.domain, {})
        gpu_mult = domain_mult.get("gpu_hours", 1.0)
        cpu_mult = domain_mult.get("cpu_hours", 1.0)

        # Calculate step-based estimates
        step_estimate = self._estimate_from_steps(experiment.steps)

        # Combine estimates
        gpu_hours = max(base["gpu_hours"] * gpu_mult, step_estimate.get("gpu_hours", 0))
        cpu_hours = max(base["cpu_hours"] * cpu_mult, step_estimate.get("cpu_hours", 0))

        # Estimate memory and storage
        memory_gb = self._estimate_memory(experiment)
        storage_gb = self._estimate_storage(experiment)

        # Estimate duration
        duration = self._estimate_duration(gpu_hours, cpu_hours, experiment)

        # Calculate cost
        cost = self._calculate_cost(gpu_hours, cpu_hours, memory_gb, storage_gb, duration)

        # Determine confidence
        confidence = self._calculate_confidence(experiment, use_history)

        estimate = ResourceEstimate(
            gpu_hours=gpu_hours,
            cpu_hours=cpu_hours,
            memory_gb=memory_gb,
            storage_gb=storage_gb,
            estimated_duration_hours=duration,
            estimated_cost=cost,
            confidence=confidence,
            breakdown={
                "gpu_hours": gpu_hours,
                "cpu_hours": cpu_hours,
                "memory_gb": memory_gb,
                "storage_gb": storage_gb,
                "duration_hours": duration,
            },
            assumptions=[
                f"Based on experiment type: {experiment.experiment_type}",
                f"Domain multiplier applied: {experiment.domain}",
                f"Number of steps: {len(experiment.steps)}",
            ],
        )

        # Store in history
        self._estimation_history[experiment.experiment_id] = estimate

        return estimate

    def _get_base_estimate(self, experiment_type: str) -> dict[str, float]:
        """Get base resource estimate from experiment type."""
        type_info = EXPERIMENT_TYPES.get(experiment_type, {})
        resources = type_info.get("typical_resources", {})
        return {
            "gpu_hours": resources.get("gpu_hours", 100),
            "cpu_hours": resources.get("cpu_hours", 200),
        }

    def _estimate_from_steps(self, steps: list[ExperimentStep]) -> dict[str, float]:
        """Estimate resources from experiment steps."""
        total_gpu = 0.0
        total_cpu = 0.0

        for step in steps:
            step_type = step.step_type
            # Estimate based on step type
            if step_type == "setup":
                total_cpu += 1
            elif step_type == "data_preparation":
                total_cpu += 5
                total_gpu += 1
            elif step_type == "execution":
                # Main computation - higher estimates
                params = step.parameters
                total_gpu += params.get("gpu_hours", 50)
                total_cpu += params.get("cpu_hours", 20)
            elif step_type == "analysis":
                total_cpu += 10
                total_gpu += 5
            elif step_type == "validation":
                total_cpu += 5
                total_gpu += 2

        return {"gpu_hours": total_gpu, "cpu_hours": total_cpu}

    def _estimate_memory(self, experiment: Experiment) -> float:
        """Estimate memory requirements."""
        base_memory = 16.0  # Base 16GB

        # Adjust based on experiment type
        type_multipliers = {
            "ml_training": 4.0,
            "structure_prediction": 3.0,
            "molecular_simulation": 2.0,
            "bioinformatics_pipeline": 2.5,
        }
        mult = type_multipliers.get(experiment.experiment_type, 1.0)

        # Check explicit requirements
        for req in experiment.resource_requirements:
            if req.resource_type == ResourceType.MEMORY:
                return req.amount

        return min(base_memory * mult, self._settings.max_memory_gb)

    def _estimate_storage(self, experiment: Experiment) -> float:
        """Estimate storage requirements."""
        base_storage = 50.0  # Base 50GB

        # Adjust based on experiment type
        type_multipliers = {
            "ml_training": 5.0,
            "bioinformatics_pipeline": 10.0,
            "molecular_simulation": 3.0,
        }
        mult = type_multipliers.get(experiment.experiment_type, 1.0)

        # Check explicit requirements
        for req in experiment.resource_requirements:
            if req.resource_type == ResourceType.STORAGE:
                return req.amount

        return min(base_storage * mult, self._settings.max_storage_gb)

    def _estimate_duration(
        self,
        gpu_hours: float,
        cpu_hours: float,
        experiment: Experiment,
    ) -> float:
        """Estimate experiment duration in hours."""
        # Assume some parallelism
        gpu_parallel = 4  # Assuming 4 GPUs available
        cpu_parallel = 16  # Assuming 16 CPU cores

        gpu_duration = gpu_hours / gpu_parallel if gpu_hours > 0 else 0
        cpu_duration = cpu_hours / cpu_parallel if cpu_hours > 0 else 0

        # Take the maximum (bottleneck) plus overhead
        base_duration = max(gpu_duration, cpu_duration)
        overhead = len(experiment.steps) * 0.5  # 30 min per step overhead

        return min(base_duration + overhead, self._settings.experiment_timeout_hours)

    def _calculate_cost(
        self,
        gpu_hours: float,
        cpu_hours: float,
        memory_gb: float,
        storage_gb: float,
        duration: float,
    ) -> float:
        """Calculate estimated cost."""
        gpu_cost = gpu_hours * RESOURCE_TYPES["gpu"]["cost_per_unit"]
        cpu_cost = cpu_hours * RESOURCE_TYPES["cpu"]["cost_per_unit"]
        memory_cost = memory_gb * duration * RESOURCE_TYPES["memory"]["cost_per_unit"]
        storage_cost = storage_gb * RESOURCE_TYPES["storage"]["cost_per_unit"]

        return gpu_cost + cpu_cost + memory_cost + storage_cost

    def _calculate_confidence(
        self,
        experiment: Experiment,
        use_history: bool,
    ) -> float:
        """Calculate confidence in the estimate."""
        confidence = 0.5  # Base confidence

        # More steps = more confidence
        if len(experiment.steps) > 3:
            confidence += 0.1

        # Explicit requirements = more confidence
        if experiment.resource_requirements:
            confidence += 0.2

        # Historical data would increase confidence
        if use_history and experiment.parent_experiment_id:
            confidence += 0.15

        # Known experiment type = more confidence
        if experiment.experiment_type in EXPERIMENT_TYPES:
            confidence += 0.1

        return min(confidence, 1.0)

    async def estimate_plan(self, plan: ExperimentPlan) -> ResourceEstimate:
        """Estimate total resources for an experiment plan."""
        total_gpu = 0.0
        total_cpu = 0.0
        total_memory = 0.0
        total_storage = 0.0
        total_cost = 0.0
        total_duration = 0.0
        confidences = []

        for experiment in plan.experiments:
            est = await self.estimate_experiment(experiment)
            total_gpu += est.gpu_hours
            total_cpu += est.cpu_hours
            total_memory = max(total_memory, est.memory_gb)  # Peak memory
            total_storage += est.storage_gb
            total_cost += est.estimated_cost
            total_duration += est.estimated_duration_hours
            confidences.append(est.confidence)

        # Account for dependencies - some experiments run in parallel
        dep_graph = plan.dependencies
        parallel_factor = self._calculate_parallel_factor(plan.experiments, dep_graph)
        adjusted_duration = total_duration * parallel_factor

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

        return ResourceEstimate(
            gpu_hours=total_gpu,
            cpu_hours=total_cpu,
            memory_gb=total_memory,
            storage_gb=total_storage,
            estimated_duration_hours=adjusted_duration,
            estimated_cost=total_cost,
            confidence=avg_confidence,
            breakdown={
                "total_experiments": len(plan.experiments),
                "parallel_factor": parallel_factor,
                "per_experiment_avg_duration": total_duration / max(len(plan.experiments), 1),
            },
            assumptions=[
                f"Total experiments: {len(plan.experiments)}",
                f"Parallel factor: {parallel_factor:.2f}",
                "Peak memory requirement used",
            ],
        )

    def _calculate_parallel_factor(
        self,
        experiments: list[Experiment],
        dependencies: dict[str, list[str]],
    ) -> float:
        """Calculate how much parallelism is possible."""
        if not experiments:
            return 1.0

        # Simple heuristic: count dependency depth
        max_depth = 1
        for exp_id, deps in dependencies.items():
            depth = len(deps) + 1
            max_depth = max(max_depth, depth)

        # Factor is depth / total experiments
        return max_depth / len(experiments)

    async def compare_estimates(
        self,
        experiments: list[Experiment],
    ) -> list[dict[str, Any]]:
        """Compare resource estimates for multiple experiments."""
        results = []
        for exp in experiments:
            est = await self.estimate_experiment(exp)
            results.append({
                "experiment_id": exp.experiment_id,
                "experiment_name": exp.name,
                "estimate": est.to_dict(),
                "cost_efficiency": est.gpu_hours / max(est.estimated_cost, 0.01),
            })

        # Sort by cost
        results.sort(key=lambda x: x["estimate"]["estimated_cost"])
        return results


class ExperimentScheduler:
    """Schedules experiments for execution."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._resource_estimator = ResourceEstimator()

        # Scheduling data structures
        self._pending_queue: list[ScheduledExperiment] = []  # Priority heap
        self._running: dict[str, ScheduledExperiment] = {}
        self._completed: dict[str, ScheduledExperiment] = {}
        self._failed: dict[str, ScheduledExperiment] = {}

        # Resource pools
        self._resource_pools: dict[str, ResourcePool] = {}
        self._default_pool = ResourcePool(
            name="default",
            gpu_available=1000,
            cpu_available=10000,
            memory_available_gb=256,
            storage_available_gb=1000,
            gpu_total=1000,
            cpu_total=10000,
            memory_total_gb=256,
            storage_total_gb=1000,
        )
        self._resource_pools["default"] = self._default_pool

    @property
    def resource_estimator(self) -> ResourceEstimator:
        """Get the resource estimator."""
        return self._resource_estimator

    async def schedule_experiment(
        self,
        experiment: Experiment,
        priority: int | None = None,
        deadline: datetime | None = None,
    ) -> ScheduledExperiment:
        """Schedule an experiment for execution."""
        # Estimate resources
        estimate = await self._resource_estimator.estimate_experiment(experiment)

        # Create scheduled experiment
        scheduled = ScheduledExperiment(
            experiment_id=experiment.experiment_id,
            experiment=experiment,
            priority=priority or experiment.priority,
            resource_estimate=estimate,
            status=ScheduleStatus.PENDING,
        )

        # Calculate scheduled start
        start_time = await self._find_earliest_slot(estimate, deadline)
        scheduled.scheduled_start = start_time
        scheduled.estimated_end = start_time + timedelta(hours=estimate.estimated_duration_hours)

        # Add to queue
        heapq.heappush(self._pending_queue, scheduled)

        return scheduled

    async def schedule_plan(
        self,
        plan: ExperimentPlan,
    ) -> list[ScheduledExperiment]:
        """Schedule all experiments in a plan."""
        scheduled_experiments = []
        scheduled_by_id: dict[str, ScheduledExperiment] = {}

        # Sort experiments by dependencies
        sorted_experiments = self._topological_sort(plan.experiments, plan.dependencies)

        for experiment in sorted_experiments:
            # Get dependencies' scheduled end times
            dep_ids = plan.dependencies.get(experiment.experiment_id, [])
            min_start = datetime.utcnow()

            for dep_id in dep_ids:
                if dep_id in scheduled_by_id:
                    dep_scheduled = scheduled_by_id[dep_id]
                    if dep_scheduled.estimated_end:
                        min_start = max(min_start, dep_scheduled.estimated_end)

            # Schedule experiment
            scheduled = await self.schedule_experiment(
                experiment,
                priority=experiment.priority,
                deadline=plan.end_date,
            )

            # Adjust start time based on dependencies
            if scheduled.scheduled_start and scheduled.scheduled_start < min_start:
                scheduled.scheduled_start = min_start
                if scheduled.resource_estimate:
                    duration = scheduled.resource_estimate.estimated_duration_hours
                    scheduled.estimated_end = min_start + timedelta(hours=duration)

            scheduled_experiments.append(scheduled)
            scheduled_by_id[experiment.experiment_id] = scheduled

        return scheduled_experiments

    def _topological_sort(
        self,
        experiments: list[Experiment],
        dependencies: dict[str, list[str]],
    ) -> list[Experiment]:
        """Sort experiments by dependencies (topological order)."""
        exp_by_id = {exp.experiment_id: exp for exp in experiments}
        visited = set()
        result = []

        def visit(exp_id: str) -> None:
            if exp_id in visited:
                return
            visited.add(exp_id)

            # Visit dependencies first
            for dep_id in dependencies.get(exp_id, []):
                if dep_id in exp_by_id:
                    visit(dep_id)

            if exp_id in exp_by_id:
                result.append(exp_by_id[exp_id])

        for exp in experiments:
            visit(exp.experiment_id)

        return result

    async def _find_earliest_slot(
        self,
        estimate: ResourceEstimate,
        deadline: datetime | None = None,
    ) -> datetime:
        """Find earliest available time slot for experiment."""
        # Simple implementation: check current running experiments
        current_time = datetime.utcnow()

        # Check if we have enough resources now
        pool = self._default_pool
        if (
            pool.gpu_available >= estimate.gpu_hours
            and pool.cpu_available >= estimate.cpu_hours
            and pool.memory_available_gb >= estimate.memory_gb
            and pool.storage_available_gb >= estimate.storage_gb
        ):
            return current_time

        # Find when resources become available
        earliest = current_time
        for scheduled in self._running.values():
            if scheduled.estimated_end and scheduled.estimated_end > earliest:
                earliest = scheduled.estimated_end

        return earliest

    async def start_experiment(self, schedule_id: str) -> ScheduledExperiment | None:
        """Start a scheduled experiment."""
        # Find in pending queue
        scheduled = None
        for i, item in enumerate(self._pending_queue):
            if item.schedule_id == schedule_id:
                scheduled = item
                self._pending_queue.pop(i)
                heapq.heapify(self._pending_queue)
                break

        if not scheduled:
            return None

        # Check resource availability
        if not await self._can_allocate_resources(scheduled):
            # Return to queue
            heapq.heappush(self._pending_queue, scheduled)
            return None

        # Allocate resources
        await self._allocate_resources(scheduled)

        # Update status
        scheduled.status = ScheduleStatus.RUNNING
        scheduled.started_at = datetime.utcnow()

        # Move to running
        self._running[schedule_id] = scheduled

        return scheduled

    async def _can_allocate_resources(self, scheduled: ScheduledExperiment) -> bool:
        """Check if resources can be allocated."""
        estimate = scheduled.resource_estimate
        if not estimate:
            return True

        pool = self._resource_pools.get(scheduled.assigned_pool or "default", self._default_pool)

        return (
            pool.gpu_available >= estimate.gpu_hours
            and pool.cpu_available >= estimate.cpu_hours
            and pool.memory_available_gb >= estimate.memory_gb
            and pool.storage_available_gb >= estimate.storage_gb
        )

    async def _allocate_resources(self, scheduled: ScheduledExperiment) -> None:
        """Allocate resources for experiment."""
        estimate = scheduled.resource_estimate
        if not estimate:
            return

        pool_name = scheduled.assigned_pool or "default"
        pool = self._resource_pools.get(pool_name, self._default_pool)

        pool.gpu_available -= estimate.gpu_hours
        pool.cpu_available -= estimate.cpu_hours
        # Memory is shared/reusable, storage is allocated
        pool.storage_available_gb -= estimate.storage_gb

    async def _release_resources(self, scheduled: ScheduledExperiment) -> None:
        """Release resources from completed experiment."""
        estimate = scheduled.resource_estimate
        if not estimate:
            return

        pool_name = scheduled.assigned_pool or "default"
        pool = self._resource_pools.get(pool_name, self._default_pool)

        pool.gpu_available += estimate.gpu_hours
        pool.cpu_available += estimate.cpu_hours
        pool.storage_available_gb += estimate.storage_gb

    async def complete_experiment(
        self,
        schedule_id: str,
        success: bool = True,
    ) -> ScheduledExperiment | None:
        """Mark experiment as completed."""
        scheduled = self._running.pop(schedule_id, None)
        if not scheduled:
            return None

        # Release resources
        await self._release_resources(scheduled)

        # Update status
        scheduled.completed_at = datetime.utcnow()
        if success:
            scheduled.status = ScheduleStatus.COMPLETED
            self._completed[schedule_id] = scheduled
        else:
            scheduled.status = ScheduleStatus.FAILED
            self._failed[schedule_id] = scheduled

        return scheduled

    async def cancel_experiment(self, schedule_id: str) -> ScheduledExperiment | None:
        """Cancel a scheduled or running experiment."""
        # Check pending queue
        for i, item in enumerate(self._pending_queue):
            if item.schedule_id == schedule_id:
                scheduled = item
                self._pending_queue.pop(i)
                heapq.heapify(self._pending_queue)
                scheduled.status = ScheduleStatus.CANCELLED
                return scheduled

        # Check running
        if schedule_id in self._running:
            scheduled = self._running.pop(schedule_id)
            await self._release_resources(scheduled)
            scheduled.status = ScheduleStatus.CANCELLED
            return scheduled

        return None

    async def get_next_experiment(self) -> ScheduledExperiment | None:
        """Get next experiment to run based on priority."""
        if not self._pending_queue:
            return None

        # Check if we're at max concurrent
        if len(self._running) >= self._settings.max_concurrent_experiments:
            return None

        # Peek at highest priority
        scheduled = self._pending_queue[0]

        # Check if it can be started now
        if await self._can_allocate_resources(scheduled):
            heapq.heappop(self._pending_queue)
            return scheduled

        return None

    async def get_queue_status(self) -> dict[str, Any]:
        """Get current queue status."""
        return {
            "pending_count": len(self._pending_queue),
            "running_count": len(self._running),
            "completed_count": len(self._completed),
            "failed_count": len(self._failed),
            "max_concurrent": self._settings.max_concurrent_experiments,
            "pending": [s.to_dict() for s in self._pending_queue[:10]],
            "running": [s.to_dict() for s in self._running.values()],
        }

    async def get_resource_status(self) -> dict[str, Any]:
        """Get resource pool status."""
        return {
            pool_name: {
                **pool.to_dict(),
                "utilization": pool.utilization(),
            }
            for pool_name, pool in self._resource_pools.items()
        }

    async def get_scheduled_experiment(
        self,
        schedule_id: str,
    ) -> ScheduledExperiment | None:
        """Get a scheduled experiment by ID."""
        # Check pending queue
        for item in self._pending_queue:
            if item.schedule_id == schedule_id:
                return item

        # Check running
        if schedule_id in self._running:
            return self._running[schedule_id]

        # Check completed
        if schedule_id in self._completed:
            return self._completed[schedule_id]

        # Check failed
        if schedule_id in self._failed:
            return self._failed[schedule_id]

        return None

    async def reschedule_experiment(
        self,
        schedule_id: str,
        new_priority: int | None = None,
        new_start: datetime | None = None,
    ) -> ScheduledExperiment | None:
        """Reschedule an experiment with new parameters."""
        # Find and remove from pending queue
        scheduled = None
        for i, item in enumerate(self._pending_queue):
            if item.schedule_id == schedule_id:
                scheduled = item
                self._pending_queue.pop(i)
                heapq.heapify(self._pending_queue)
                break

        if not scheduled:
            return None

        # Update parameters
        if new_priority is not None:
            scheduled.priority = new_priority
        if new_start is not None:
            scheduled.scheduled_start = new_start
            if scheduled.resource_estimate:
                duration = scheduled.resource_estimate.estimated_duration_hours
                scheduled.estimated_end = new_start + timedelta(hours=duration)

        # Re-add to queue
        heapq.heappush(self._pending_queue, scheduled)

        return scheduled

    def add_resource_pool(self, pool: ResourcePool) -> None:
        """Add a resource pool."""
        self._resource_pools[pool.pool_id] = pool

    def remove_resource_pool(self, pool_id: str) -> bool:
        """Remove a resource pool."""
        if pool_id in self._resource_pools and pool_id != "default":
            del self._resource_pools[pool_id]
            return True
        return False


# Singleton instance
_scheduler: ExperimentScheduler | None = None


def get_scheduler() -> ExperimentScheduler:
    """Get or create experiment scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = ExperimentScheduler()
    return _scheduler


__all__ = [
    "ScheduleStatus",
    "ResourcePool",
    "ScheduledExperiment",
    "ResourceEstimator",
    "ExperimentScheduler",
    "get_scheduler",
]

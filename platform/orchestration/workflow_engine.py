"""Research workflow engine for managing multi-step research processes."""

from datetime import datetime, timedelta
from typing import Any, Callable
from uuid import uuid4

from platform.orchestration.base import (
    Claim,
    ClaimStatus,
    ClaimVerificationResult,
    Priority,
    ResearchTask,
    ResearchWorkflow,
    TaskStatus,
    WorkflowStatus,
    WorkflowStep,
)
from platform.orchestration.config import (
    TASK_TYPES,
    WORKFLOW_TEMPLATES,
    get_settings,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class WorkflowEngine:
    """
    Engine for managing research workflows.

    Handles:
    - Workflow creation from templates
    - Step and task management
    - Dependency resolution
    - State transitions
    - Progress tracking
    """

    def __init__(self):
        """Initialize workflow engine."""
        self._workflows: dict[str, ResearchWorkflow] = {}
        self._step_handlers: dict[str, Callable] = {}

    async def create_workflow(
        self,
        template_name: str,
        name: str,
        description: str = "",
        claims: list[Claim] | None = None,
        context: dict[str, Any] | None = None,
        owner_agent_id: str = "",
        priority: Priority = Priority.NORMAL,
    ) -> ResearchWorkflow:
        """
        Create a workflow from a template.

        Args:
            template_name: Name of workflow template
            name: Workflow name
            description: Workflow description
            claims: Initial claims to process
            context: Additional context
            owner_agent_id: Agent owning this workflow
            priority: Workflow priority

        Returns:
            Created ResearchWorkflow
        """
        if template_name not in WORKFLOW_TEMPLATES:
            raise ValueError(f"Unknown workflow template: {template_name}")

        template = WORKFLOW_TEMPLATES[template_name]

        workflow = ResearchWorkflow(
            workflow_id=str(uuid4()),
            name=name,
            description=description or template["description"],
            template=template_name,
            status=WorkflowStatus.PENDING,
            priority=priority,
            owner_agent_id=owner_agent_id,
            claims=claims or [],
            context=context or {},
            timeout_hours=settings.workflow_timeout_hours,
        )

        # Create steps from template
        for order, step_name in enumerate(template["steps"]):
            step = WorkflowStep(
                step_id=str(uuid4()),
                step_name=step_name,
                step_type=step_name,
                order=order,
                status=TaskStatus.PENDING,
            )

            # Set up step dependencies
            if order > 0:
                step.depends_on = [workflow.steps[order - 1].step_id]

            workflow.steps.append(step)

        self._workflows[workflow.workflow_id] = workflow

        logger.info(
            "workflow_created",
            workflow_id=workflow.workflow_id,
            template=template_name,
            num_steps=len(workflow.steps),
        )

        return workflow

    async def start_workflow(self, workflow_id: str) -> ResearchWorkflow:
        """
        Start a workflow execution.

        Args:
            workflow_id: ID of workflow to start

        Returns:
            Updated workflow
        """
        workflow = self._get_workflow(workflow_id)

        if workflow.status != WorkflowStatus.PENDING:
            raise ValueError(f"Workflow {workflow_id} is not in pending state")

        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.utcnow()

        # Start first step
        if workflow.steps:
            await self._start_step(workflow, workflow.steps[0])

        logger.info("workflow_started", workflow_id=workflow_id)

        return workflow

    async def advance_workflow(self, workflow_id: str) -> ResearchWorkflow:
        """
        Advance workflow to next step if current step is complete.

        Args:
            workflow_id: ID of workflow

        Returns:
            Updated workflow
        """
        workflow = self._get_workflow(workflow_id)

        if workflow.status != WorkflowStatus.RUNNING:
            return workflow

        # Check timeout
        if self._is_timed_out(workflow):
            workflow.status = WorkflowStatus.TIMEOUT
            workflow.completed_at = datetime.utcnow()
            workflow.error_message = "Workflow timed out"
            logger.warning("workflow_timeout", workflow_id=workflow_id)
            return workflow

        # Find current step
        current_step = workflow.current_step

        if current_step is None:
            # All steps complete
            workflow.status = WorkflowStatus.COMPLETED
            workflow.completed_at = datetime.utcnow()
            logger.info("workflow_completed", workflow_id=workflow_id)
            return workflow

        # Check if current step is complete
        if current_step.status == TaskStatus.COMPLETED:
            # Move to next step
            next_step = self._get_next_step(workflow, current_step)
            if next_step:
                await self._start_step(workflow, next_step)
            else:
                workflow.status = WorkflowStatus.COMPLETED
                workflow.completed_at = datetime.utcnow()

        elif current_step.status == TaskStatus.FAILED:
            workflow.status = WorkflowStatus.FAILED
            workflow.completed_at = datetime.utcnow()
            workflow.error_message = f"Step {current_step.step_name} failed"

        return workflow

    async def complete_step(
        self,
        workflow_id: str,
        step_id: str,
        outputs: dict[str, Any] | None = None,
        status: TaskStatus = TaskStatus.COMPLETED,
    ) -> ResearchWorkflow:
        """
        Mark a step as complete.

        Args:
            workflow_id: Workflow ID
            step_id: Step ID
            outputs: Step outputs
            status: Final status

        Returns:
            Updated workflow
        """
        workflow = self._get_workflow(workflow_id)
        step = self._get_step(workflow, step_id)

        step.status = status
        step.outputs = outputs or {}

        # Mark all step tasks as complete
        for task_id in step.task_ids:
            if task_id in workflow.tasks:
                workflow.tasks[task_id].status = status
                workflow.tasks[task_id].completed_at = datetime.utcnow()
                workflow.tasks[task_id].outputs = outputs or {}

        logger.info(
            "step_completed",
            workflow_id=workflow_id,
            step_id=step_id,
            status=status.value,
        )

        # Try to advance workflow
        return await self.advance_workflow(workflow_id)

    async def fail_step(
        self,
        workflow_id: str,
        step_id: str,
        error_message: str,
    ) -> ResearchWorkflow:
        """
        Mark a step as failed.

        Args:
            workflow_id: Workflow ID
            step_id: Step ID
            error_message: Error description

        Returns:
            Updated workflow
        """
        workflow = self._get_workflow(workflow_id)
        step = self._get_step(workflow, step_id)

        step.status = TaskStatus.FAILED

        # Mark tasks as failed
        for task_id in step.task_ids:
            if task_id in workflow.tasks:
                task = workflow.tasks[task_id]
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.utcnow()
                task.error_message = error_message

        logger.warning(
            "step_failed",
            workflow_id=workflow_id,
            step_id=step_id,
            error=error_message,
        )

        return await self.advance_workflow(workflow_id)

    async def add_claim_result(
        self,
        workflow_id: str,
        result: ClaimVerificationResult,
    ) -> None:
        """
        Add a claim verification result to workflow.

        Args:
            workflow_id: Workflow ID
            result: Verification result
        """
        workflow = self._get_workflow(workflow_id)
        workflow.results.append(result)

        logger.info(
            "claim_result_added",
            workflow_id=workflow_id,
            claim_id=result.claim_id,
            verified=result.verified,
        )

    async def create_task(
        self,
        workflow_id: str,
        step_id: str,
        task_type: str,
        name: str,
        inputs: dict[str, Any] | None = None,
        dependencies: list[str] | None = None,
    ) -> ResearchTask:
        """
        Create a task within a workflow step.

        Args:
            workflow_id: Workflow ID
            step_id: Step ID
            task_type: Type of task
            name: Task name
            inputs: Task inputs
            dependencies: Task dependencies

        Returns:
            Created task
        """
        workflow = self._get_workflow(workflow_id)
        step = self._get_step(workflow, step_id)

        task_config = TASK_TYPES.get(task_type, {})

        task = ResearchTask(
            task_id=str(uuid4()),
            task_type=task_type,
            name=name,
            workflow_id=workflow_id,
            inputs=inputs or {},
            dependencies=dependencies or [],
            priority=workflow.priority,
            timeout_minutes=task_config.get("timeout_minutes", settings.task_timeout_minutes),
            max_retries=task_config.get("retries", settings.max_task_retries),
        )

        workflow.tasks[task.task_id] = task
        step.task_ids.append(task.task_id)

        return task

    async def pause_workflow(self, workflow_id: str) -> ResearchWorkflow:
        """Pause a running workflow."""
        workflow = self._get_workflow(workflow_id)

        if workflow.status == WorkflowStatus.RUNNING:
            workflow.status = WorkflowStatus.PAUSED
            logger.info("workflow_paused", workflow_id=workflow_id)

        return workflow

    async def resume_workflow(self, workflow_id: str) -> ResearchWorkflow:
        """Resume a paused workflow."""
        workflow = self._get_workflow(workflow_id)

        if workflow.status == WorkflowStatus.PAUSED:
            workflow.status = WorkflowStatus.RUNNING
            logger.info("workflow_resumed", workflow_id=workflow_id)

        return workflow

    async def cancel_workflow(self, workflow_id: str) -> ResearchWorkflow:
        """Cancel a workflow."""
        workflow = self._get_workflow(workflow_id)

        if not workflow.is_complete:
            workflow.status = WorkflowStatus.CANCELLED
            workflow.completed_at = datetime.utcnow()

            # Cancel all pending tasks
            for task in workflow.tasks.values():
                if not task.is_complete:
                    task.status = TaskStatus.CANCELLED
                    task.completed_at = datetime.utcnow()

            logger.info("workflow_cancelled", workflow_id=workflow_id)

        return workflow

    def get_workflow(self, workflow_id: str) -> ResearchWorkflow | None:
        """Get a workflow by ID."""
        return self._workflows.get(workflow_id)

    def get_workflow_status(self, workflow_id: str) -> dict[str, Any]:
        """Get workflow status summary."""
        workflow = self._get_workflow(workflow_id)

        return {
            "workflow_id": workflow.workflow_id,
            "status": workflow.status.value,
            "progress_percent": workflow.progress_percent,
            "current_step": workflow.current_step.step_name if workflow.current_step else None,
            "total_steps": len(workflow.steps),
            "completed_steps": sum(1 for s in workflow.steps if s.status == TaskStatus.COMPLETED),
            "total_claims": len(workflow.claims),
            "verified_claims": sum(1 for r in workflow.results if r.verified),
            "execution_time_seconds": workflow.execution_time_seconds,
        }

    def get_ready_tasks(self, workflow_id: str) -> list[ResearchTask]:
        """Get tasks that are ready to execute (dependencies satisfied)."""
        workflow = self._get_workflow(workflow_id)
        ready = []

        for task in workflow.tasks.values():
            if task.status != TaskStatus.PENDING:
                continue

            # Check dependencies
            deps_satisfied = all(
                workflow.tasks.get(dep_id, ResearchTask()).status == TaskStatus.COMPLETED
                for dep_id in task.dependencies
            )

            if deps_satisfied:
                ready.append(task)

        return ready

    async def _start_step(self, workflow: ResearchWorkflow, step: WorkflowStep) -> None:
        """Start execution of a workflow step."""
        step.status = TaskStatus.RUNNING

        # Create initial task for the step
        task = await self.create_task(
            workflow_id=workflow.workflow_id,
            step_id=step.step_id,
            task_type=step.step_type,
            name=f"Execute {step.step_name}",
            inputs=step.inputs,
        )

        logger.info(
            "step_started",
            workflow_id=workflow.workflow_id,
            step_id=step.step_id,
            step_name=step.step_name,
        )

    def _get_workflow(self, workflow_id: str) -> ResearchWorkflow:
        """Get workflow or raise error."""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        return workflow

    def _get_step(self, workflow: ResearchWorkflow, step_id: str) -> WorkflowStep:
        """Get step or raise error."""
        for step in workflow.steps:
            if step.step_id == step_id:
                return step
        raise ValueError(f"Step not found: {step_id}")

    def _get_next_step(
        self,
        workflow: ResearchWorkflow,
        current_step: WorkflowStep,
    ) -> WorkflowStep | None:
        """Get the next step after current."""
        for step in workflow.steps:
            if step.order == current_step.order + 1:
                return step
        return None

    def _is_timed_out(self, workflow: ResearchWorkflow) -> bool:
        """Check if workflow has timed out."""
        if not workflow.started_at:
            return False
        timeout = timedelta(hours=workflow.timeout_hours)
        return datetime.utcnow() > workflow.started_at + timeout

    def register_step_handler(self, step_type: str, handler: Callable) -> None:
        """Register a handler for a step type."""
        self._step_handlers[step_type] = handler

    def get_templates(self) -> list[dict[str, Any]]:
        """Get available workflow templates."""
        return [
            {
                "name": name,
                "description": template["description"],
                "steps": template["steps"],
            }
            for name, template in WORKFLOW_TEMPLATES.items()
        ]


# Singleton instance
_engine_instance: WorkflowEngine | None = None


def get_workflow_engine() -> WorkflowEngine:
    """Get singleton WorkflowEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = WorkflowEngine()
    return _engine_instance

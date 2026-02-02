"""REST API endpoints for Experiment Planning."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from platform.experiments.base import ExperimentStatus
from platform.experiments.service import get_experiment_service


router = APIRouter(prefix="/experiments", tags=["experiments"])


# ===========================================
# REQUEST/RESPONSE MODELS
# ===========================================


class HypothesisGenerateRequest(BaseModel):
    """Request to generate hypotheses."""

    domain: str = Field(..., description="Research domain")
    topic: str = Field(..., description="Topic or gap description")
    count: int = Field(default=3, ge=1, le=10, description="Number of hypotheses to generate")
    hypothesis_type: str | None = Field(default=None, description="Type: causal, comparative, etc.")


class HypothesisResponse(BaseModel):
    """Hypothesis response."""

    hypothesis_id: str
    title: str
    statement: str
    hypothesis_type: str
    variables: list[str]
    predictions: list[str]
    status: str
    confidence: float
    priority: int


class ExperimentCreateRequest(BaseModel):
    """Request to create an experiment."""

    name: str = Field(..., description="Experiment name")
    description: str = Field(..., description="Experiment description")
    domain: str = Field(..., description="Research domain")
    experiment_type: str = Field(..., description="Type of experiment")
    created_by: str = Field(default="api", description="Creator")
    hypothesis_ids: list[str] | None = Field(default=None, description="Hypothesis IDs to test")


class ExperimentDesignRequest(BaseModel):
    """Request to design an experiment."""

    variables: list[dict[str, Any]] | None = Field(default=None, description="Variables to add")
    steps: list[dict[str, Any]] | None = Field(default=None, description="Steps to add")
    config: dict[str, Any] | None = Field(default=None, description="Configuration")


class ExperimentScheduleRequest(BaseModel):
    """Request to schedule an experiment."""

    priority: int | None = Field(default=None, ge=1, le=10, description="Priority (1=highest)")
    deadline: datetime | None = Field(default=None, description="Deadline for completion")


class ExperimentCompleteRequest(BaseModel):
    """Request to complete an experiment."""

    results: dict[str, Any] = Field(..., description="Experiment results")
    success: bool = Field(default=True, description="Whether experiment succeeded")


class PlanCreateRequest(BaseModel):
    """Request to create an experiment plan."""

    name: str = Field(..., description="Plan name")
    description: str = Field(..., description="Plan description")
    objective: str = Field(..., description="Research objective")
    domain: str = Field(..., description="Research domain")
    created_by: str = Field(default="api", description="Creator")


class PlanAddExperimentRequest(BaseModel):
    """Request to add experiment to plan."""

    experiment_id: str = Field(..., description="Experiment ID to add")
    dependencies: list[str] | None = Field(default=None, description="Dependency experiment IDs")


class CheckpointCreateRequest(BaseModel):
    """Request to create a checkpoint."""

    step_id: str = Field(..., description="Current step ID")
    state: dict[str, Any] = Field(..., description="State to save")
    metrics: dict[str, float] | None = Field(default=None, description="Current metrics")


class ExperimentResponse(BaseModel):
    """Experiment response."""

    experiment_id: str
    name: str
    description: str
    experiment_type: str
    domain: str
    status: str
    priority: int
    progress: float
    created_by: str
    created_at: datetime
    updated_at: datetime


class PlanResponse(BaseModel):
    """Plan response."""

    plan_id: str
    name: str
    description: str
    objective: str
    domain: str
    status: str
    experiment_count: int
    created_by: str
    created_at: datetime


class StatsResponse(BaseModel):
    """Statistics response."""

    total_experiments: int
    draft_count: int
    planned_count: int
    queued_count: int
    running_count: int
    completed_count: int
    failed_count: int
    total_hypotheses: int
    supported_hypotheses: int
    refuted_hypotheses: int
    total_plans: int
    total_gpu_hours_used: float
    total_cpu_hours_used: float
    avg_experiment_duration: float


# ===========================================
# HYPOTHESIS ENDPOINTS
# ===========================================


@router.post("/hypotheses/generate", response_model=list[HypothesisResponse])
async def generate_hypotheses(request: HypothesisGenerateRequest):
    """Generate hypotheses for a domain and topic."""
    service = get_experiment_service()

    hypotheses = await service.generate_hypotheses(
        domain=request.domain,
        topic=request.topic,
        count=request.count,
        hypothesis_type=request.hypothesis_type,
    )

    return [
        HypothesisResponse(
            hypothesis_id=h.hypothesis_id,
            title=h.title,
            statement=h.statement,
            hypothesis_type=h.hypothesis_type,
            variables=h.variables,
            predictions=h.predictions,
            status=h.status.value,
            confidence=h.confidence,
            priority=h.priority,
        )
        for h in hypotheses
    ]


@router.post("/hypotheses/validate")
async def validate_hypothesis(hypothesis_data: dict[str, Any]):
    """Validate a hypothesis."""
    from platform.experiments.base import Hypothesis

    service = get_experiment_service()
    hypothesis = Hypothesis.from_dict(hypothesis_data)
    result = await service.validate_hypothesis(hypothesis)
    return result


# ===========================================
# EXPERIMENT ENDPOINTS
# ===========================================


@router.post("", response_model=ExperimentResponse)
async def create_experiment(request: ExperimentCreateRequest):
    """Create a new experiment."""
    service = get_experiment_service()

    experiment = await service.create_experiment(
        name=request.name,
        description=request.description,
        domain=request.domain,
        experiment_type=request.experiment_type,
        created_by=request.created_by,
    )

    return ExperimentResponse(
        experiment_id=experiment.experiment_id,
        name=experiment.name,
        description=experiment.description,
        experiment_type=experiment.experiment_type,
        domain=experiment.domain,
        status=experiment.status.value,
        priority=experiment.priority,
        progress=experiment.progress,
        created_by=experiment.created_by,
        created_at=experiment.created_at,
        updated_at=experiment.updated_at,
    )


@router.get("/{experiment_id}")
async def get_experiment(experiment_id: str):
    """Get an experiment by ID."""
    service = get_experiment_service()
    experiment = await service.get_experiment(experiment_id)

    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    return experiment.to_dict()


@router.get("")
async def list_experiments(
    domain: str | None = Query(default=None, description="Filter by domain"),
    status: str | None = Query(default=None, description="Filter by status"),
    experiment_type: str | None = Query(default=None, description="Filter by type"),
    created_by: str | None = Query(default=None, description="Filter by creator"),
    limit: int = Query(default=50, ge=1, le=100, description="Limit results"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
):
    """List experiments with filters."""
    service = get_experiment_service()

    exp_status = ExperimentStatus(status) if status else None

    experiments = await service.list_experiments(
        domain=domain,
        status=exp_status,
        experiment_type=experiment_type,
        created_by=created_by,
        limit=limit,
        offset=offset,
    )

    return {
        "experiments": [e.to_dict() for e in experiments],
        "total": len(experiments),
        "limit": limit,
        "offset": offset,
    }


@router.post("/{experiment_id}/design")
async def design_experiment(experiment_id: str, request: ExperimentDesignRequest):
    """Complete experiment design with variables, steps, and config."""
    service = get_experiment_service()

    try:
        experiment = await service.design_experiment(
            experiment_id=experiment_id,
            variables=request.variables,
            steps=request.steps,
            config=request.config,
        )
        return experiment.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{experiment_id}/validate")
async def validate_experiment_design(experiment_id: str):
    """Validate experiment design."""
    service = get_experiment_service()

    try:
        result = await service.validate_experiment_design(experiment_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{experiment_id}/clone")
async def clone_experiment(
    experiment_id: str,
    new_name: str | None = Query(default=None, description="Name for cloned experiment"),
):
    """Clone an existing experiment."""
    service = get_experiment_service()

    try:
        cloned = await service.clone_experiment(experiment_id, new_name=new_name)
        return cloned.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{experiment_id}/search")
async def search_experiments(
    query: str = Query(..., description="Search query"),
    limit: int = Query(default=20, ge=1, le=100, description="Limit results"),
):
    """Search experiments by name or description."""
    service = get_experiment_service()
    experiments = await service.search_experiments(query, limit=limit)
    return {"experiments": [e.to_dict() for e in experiments], "total": len(experiments)}


# ===========================================
# SCHEDULING ENDPOINTS
# ===========================================


@router.post("/{experiment_id}/schedule")
async def schedule_experiment(experiment_id: str, request: ExperimentScheduleRequest):
    """Schedule an experiment for execution."""
    service = get_experiment_service()

    try:
        scheduled = await service.schedule_experiment(
            experiment_id=experiment_id,
            priority=request.priority,
            deadline=request.deadline,
        )
        return scheduled.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{experiment_id}/start")
async def start_experiment(experiment_id: str):
    """Start an experiment."""
    service = get_experiment_service()

    try:
        experiment, scheduled = await service.start_experiment(experiment_id)
        return {
            "experiment": experiment.to_dict(),
            "scheduled": scheduled.to_dict() if scheduled else None,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{experiment_id}/complete")
async def complete_experiment(experiment_id: str, request: ExperimentCompleteRequest):
    """Complete an experiment with results."""
    service = get_experiment_service()

    try:
        result = await service.complete_experiment(
            experiment_id=experiment_id,
            results=request.results,
            success=request.success,
        )
        return result.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{experiment_id}/pause")
async def pause_experiment(experiment_id: str):
    """Pause a running experiment."""
    service = get_experiment_service()

    try:
        experiment = await service.pause_experiment(experiment_id)
        return experiment.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{experiment_id}/resume")
async def resume_experiment(experiment_id: str):
    """Resume a paused experiment."""
    service = get_experiment_service()

    try:
        experiment = await service.resume_experiment(experiment_id)
        return experiment.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{experiment_id}/cancel")
async def cancel_experiment(experiment_id: str):
    """Cancel an experiment."""
    service = get_experiment_service()

    try:
        experiment = await service.cancel_experiment(experiment_id)
        return experiment.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ===========================================
# CHECKPOINT ENDPOINTS
# ===========================================


@router.post("/{experiment_id}/checkpoints")
async def create_checkpoint(experiment_id: str, request: CheckpointCreateRequest):
    """Create a checkpoint for experiment state."""
    service = get_experiment_service()

    try:
        checkpoint = await service.create_checkpoint(
            experiment_id=experiment_id,
            step_id=request.step_id,
            state=request.state,
            metrics=request.metrics,
        )
        return checkpoint.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{experiment_id}/checkpoints")
async def get_checkpoints(experiment_id: str):
    """Get checkpoints for an experiment."""
    service = get_experiment_service()
    checkpoints = await service.get_checkpoints(experiment_id)
    return {"checkpoints": [c.to_dict() for c in checkpoints]}


@router.post("/{experiment_id}/checkpoints/{checkpoint_id}/restore")
async def restore_from_checkpoint(experiment_id: str, checkpoint_id: str):
    """Restore experiment state from checkpoint."""
    service = get_experiment_service()

    state = await service.restore_from_checkpoint(experiment_id, checkpoint_id)
    if not state:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    return {"state": state}


# ===========================================
# RESULTS ENDPOINTS
# ===========================================


@router.get("/{experiment_id}/results")
async def get_experiment_results(experiment_id: str):
    """Get results for an experiment."""
    service = get_experiment_service()
    results = await service.get_results_for_experiment(experiment_id)
    return {"results": [r.to_dict() for r in results]}


@router.get("/results/{result_id}")
async def get_result(result_id: str):
    """Get a specific result by ID."""
    service = get_experiment_service()
    result = await service.get_result(result_id)

    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    return result.to_dict()


# ===========================================
# PLAN ENDPOINTS
# ===========================================


@router.post("/plans", response_model=PlanResponse)
async def create_plan(request: PlanCreateRequest):
    """Create an experiment plan."""
    service = get_experiment_service()

    plan = await service.create_plan(
        name=request.name,
        description=request.description,
        objective=request.objective,
        domain=request.domain,
        created_by=request.created_by,
    )

    return PlanResponse(
        plan_id=plan.plan_id,
        name=plan.name,
        description=plan.description,
        objective=plan.objective,
        domain=plan.domain,
        status=plan.status,
        experiment_count=len(plan.experiments),
        created_by=plan.created_by,
        created_at=plan.created_at,
    )


@router.get("/plans/{plan_id}")
async def get_plan(plan_id: str):
    """Get an experiment plan by ID."""
    service = get_experiment_service()
    plan = await service.get_plan(plan_id)

    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    return plan.to_dict()


@router.get("/plans")
async def list_plans(
    domain: str | None = Query(default=None, description="Filter by domain"),
    status: str | None = Query(default=None, description="Filter by status"),
):
    """List experiment plans."""
    service = get_experiment_service()
    plans = await service.list_plans(domain=domain, status=status)
    return {"plans": [p.to_dict() for p in plans], "total": len(plans)}


@router.post("/plans/{plan_id}/experiments")
async def add_experiment_to_plan(plan_id: str, request: PlanAddExperimentRequest):
    """Add an experiment to a plan."""
    service = get_experiment_service()

    try:
        plan = await service.add_experiment_to_plan(
            plan_id=plan_id,
            experiment_id=request.experiment_id,
            dependencies=request.dependencies,
        )
        return plan.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/plans/{plan_id}/estimate")
async def estimate_plan_resources(plan_id: str):
    """Estimate resources for a plan."""
    service = get_experiment_service()

    try:
        estimate = await service.estimate_plan_resources(plan_id)
        return estimate.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/plans/{plan_id}/schedule")
async def schedule_plan(plan_id: str):
    """Schedule all experiments in a plan."""
    service = get_experiment_service()

    try:
        scheduled = await service.schedule_plan(plan_id)
        return {"scheduled": [s.to_dict() for s in scheduled]}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ===========================================
# STATUS ENDPOINTS
# ===========================================


@router.get("/status/stats", response_model=StatsResponse)
async def get_stats():
    """Get experiment statistics."""
    service = get_experiment_service()
    stats = await service.get_stats()

    return StatsResponse(
        total_experiments=stats.total_experiments,
        draft_count=stats.draft_count,
        planned_count=stats.planned_count,
        queued_count=stats.queued_count,
        running_count=stats.running_count,
        completed_count=stats.completed_count,
        failed_count=stats.failed_count,
        total_hypotheses=stats.total_hypotheses,
        supported_hypotheses=stats.supported_hypotheses,
        refuted_hypotheses=stats.refuted_hypotheses,
        total_plans=stats.total_plans,
        total_gpu_hours_used=stats.total_gpu_hours_used,
        total_cpu_hours_used=stats.total_cpu_hours_used,
        avg_experiment_duration=stats.avg_experiment_duration,
    )


@router.get("/status/queue")
async def get_queue_status():
    """Get scheduler queue status."""
    service = get_experiment_service()
    return await service.get_queue_status()


@router.get("/status/resources")
async def get_resource_status():
    """Get resource pool status."""
    service = get_experiment_service()
    return await service.get_resource_status()


__all__ = ["router"]

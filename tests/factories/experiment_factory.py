"""Experiment test data factory."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4


def _utcnow() -> datetime:
    """Return current UTC time with timezone info."""
    return datetime.now(timezone.utc)


@dataclass
class ExperimentFactory:
    """Factory for creating Experiment test instances."""

    _counter: int = field(default=0, repr=False)

    VALID_STATUSES = [
        "pending",
        "scheduled",
        "running",
        "paused",
        "completed",
        "failed",
        "cancelled",
    ]

    VALID_DOMAINS = [
        "mathematics",
        "ml_ai",
        "computational_biology",
        "materials_science",
        "bioinformatics",
    ]

    @classmethod
    def create(
        cls,
        experiment_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        hypothesis_id: str | None = None,
        domain: str = "ml_ai",
        status: str = "pending",
        created_by: str | None = None,
        parameters: dict[str, Any] | None = None,
        metrics: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create an experiment data dictionary with sensible defaults."""
        cls._counter = getattr(cls, "_counter", 0) + 1

        return {
            "experiment_id": experiment_id or str(uuid4()),
            "name": name or f"Test Experiment {cls._counter}",
            "description": description or f"Test experiment description {cls._counter}",
            "hypothesis_id": hypothesis_id or str(uuid4()),
            "domain": domain,
            "status": status,
            "created_by": created_by or str(uuid4()),
            "parameters": parameters or {
                "learning_rate": 0.001,
                "batch_size": 32,
                "epochs": 100,
            },
            "metrics": metrics or {},
            "tags": tags or ["test", "automated"],
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
            "started_at": None,
            "completed_at": None,
            **kwargs,
        }

    @classmethod
    def create_ml_experiment(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a machine learning experiment."""
        return cls.create(
            name=kwargs.pop("name", "ML Training Experiment"),
            domain="ml_ai",
            parameters=kwargs.pop("parameters", {
                "model_type": "transformer",
                "learning_rate": 0.0001,
                "batch_size": 64,
                "epochs": 50,
                "optimizer": "adamw",
                "weight_decay": 0.01,
            }),
            tags=kwargs.pop("tags", ["ml", "training", "deep-learning"]),
            **kwargs,
        )

    @classmethod
    def create_math_experiment(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a mathematics verification experiment."""
        return cls.create(
            name=kwargs.pop("name", "Theorem Verification Experiment"),
            domain="mathematics",
            parameters=kwargs.pop("parameters", {
                "prover": "lean4",
                "timeout_seconds": 300,
                "max_depth": 10,
            }),
            tags=kwargs.pop("tags", ["mathematics", "theorem-proving"]),
            **kwargs,
        )

    @classmethod
    def create_biology_experiment(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a computational biology experiment."""
        return cls.create(
            name=kwargs.pop("name", "Protein Structure Prediction"),
            domain="computational_biology",
            parameters=kwargs.pop("parameters", {
                "model": "alphafold2",
                "sequence_length": 500,
                "use_templates": True,
            }),
            tags=kwargs.pop("tags", ["biology", "protein-folding"]),
            **kwargs,
        )

    @classmethod
    def create_running(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a running experiment."""
        experiment = cls.create(status="running", **kwargs)
        experiment["started_at"] = _utcnow() - timedelta(hours=1)
        return experiment

    @classmethod
    def create_completed(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a completed experiment."""
        experiment = cls.create(status="completed", **kwargs)
        experiment["started_at"] = _utcnow() - timedelta(hours=2)
        experiment["completed_at"] = _utcnow()
        experiment["metrics"] = kwargs.pop("metrics", {
            "accuracy": 0.95,
            "loss": 0.05,
            "duration_seconds": 3600,
        })
        return experiment

    @classmethod
    def create_failed(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a failed experiment."""
        experiment = cls.create(status="failed", **kwargs)
        experiment["started_at"] = _utcnow() - timedelta(hours=1)
        experiment["error_message"] = kwargs.pop("error_message", "Out of memory")
        return experiment

    @classmethod
    def create_batch(cls, count: int, **kwargs: Any) -> list[dict[str, Any]]:
        """Create multiple experiment instances."""
        return [cls.create(**kwargs) for _ in range(count)]


@dataclass
class ExperimentPlanFactory:
    """Factory for creating ExperimentPlan test instances."""

    _counter: int = field(default=0, repr=False)

    @classmethod
    def create(
        cls,
        plan_id: str | None = None,
        experiment_id: str | None = None,
        steps: list[dict[str, Any]] | None = None,
        resources: dict[str, Any] | None = None,
        dependencies: list[str] | None = None,
        estimated_duration_minutes: int = 60,
        priority: int = 5,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create an experiment plan data dictionary."""
        cls._counter = getattr(cls, "_counter", 0) + 1

        return {
            "plan_id": plan_id or str(uuid4()),
            "experiment_id": experiment_id or str(uuid4()),
            "steps": steps or cls._default_steps(),
            "resources": resources or {
                "cpu_cores": 4,
                "memory_gb": 16,
                "gpu_count": 1,
                "gpu_type": "nvidia-a100",
                "storage_gb": 100,
            },
            "dependencies": dependencies or [],
            "estimated_duration_minutes": estimated_duration_minutes,
            "priority": priority,
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
            **kwargs,
        }

    @classmethod
    def _default_steps(cls) -> list[dict[str, Any]]:
        """Generate default experiment steps."""
        return [
            {
                "step_id": str(uuid4()),
                "name": "Data Preparation",
                "type": "preprocessing",
                "status": "pending",
                "order": 1,
                "config": {"input_format": "csv", "output_format": "tensor"},
            },
            {
                "step_id": str(uuid4()),
                "name": "Model Training",
                "type": "training",
                "status": "pending",
                "order": 2,
                "config": {"checkpoint_interval": 1000},
            },
            {
                "step_id": str(uuid4()),
                "name": "Evaluation",
                "type": "evaluation",
                "status": "pending",
                "order": 3,
                "config": {"metrics": ["accuracy", "f1", "precision", "recall"]},
            },
        ]

    @classmethod
    def create_simple_plan(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a simple single-step plan."""
        return cls.create(
            steps=[{
                "step_id": str(uuid4()),
                "name": "Execute",
                "type": "execute",
                "status": "pending",
                "order": 1,
            }],
            resources=kwargs.pop("resources", {
                "cpu_cores": 2,
                "memory_gb": 8,
                "gpu_count": 0,
            }),
            estimated_duration_minutes=kwargs.pop("estimated_duration_minutes", 15),
            **kwargs,
        )

    @classmethod
    def create_gpu_intensive_plan(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a GPU-intensive plan for deep learning."""
        return cls.create(
            resources=kwargs.pop("resources", {
                "cpu_cores": 8,
                "memory_gb": 64,
                "gpu_count": 4,
                "gpu_type": "nvidia-a100",
                "storage_gb": 500,
            }),
            estimated_duration_minutes=kwargs.pop("estimated_duration_minutes", 480),
            priority=kwargs.pop("priority", 8),
            **kwargs,
        )

    @classmethod
    def create_with_dependencies(
        cls,
        dependency_plan_ids: list[str],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a plan with dependencies on other plans."""
        return cls.create(
            dependencies=dependency_plan_ids,
            **kwargs,
        )


@dataclass
class ExperimentResultFactory:
    """Factory for creating ExperimentResult test instances."""

    _counter: int = field(default=0, repr=False)

    @classmethod
    def create(
        cls,
        result_id: str | None = None,
        experiment_id: str | None = None,
        status: str = "completed",
        metrics: dict[str, Any] | None = None,
        outputs: dict[str, Any] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        error_message: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create an experiment result data dictionary."""
        cls._counter = getattr(cls, "_counter", 0) + 1

        return {
            "result_id": result_id or str(uuid4()),
            "experiment_id": experiment_id or str(uuid4()),
            "status": status,
            "metrics": metrics or {
                "accuracy": 0.92,
                "loss": 0.08,
                "f1_score": 0.91,
            },
            "outputs": outputs or {},
            "artifacts": artifacts or [],
            "error_message": error_message,
            "started_at": _utcnow() - timedelta(hours=1),
            "completed_at": _utcnow(),
            "duration_seconds": 3600,
            **kwargs,
        }

    @classmethod
    def create_successful(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a successful experiment result."""
        return cls.create(
            status="completed",
            metrics=kwargs.pop("metrics", {
                "accuracy": 0.95,
                "loss": 0.05,
                "f1_score": 0.94,
                "precision": 0.93,
                "recall": 0.95,
            }),
            **kwargs,
        )

    @classmethod
    def create_failed(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a failed experiment result."""
        result = cls.create(
            status="failed",
            metrics={},
            error_message=kwargs.pop("error_message", "Training diverged: NaN loss detected"),
            **kwargs,
        )
        result["completed_at"] = _utcnow()
        return result

    @classmethod
    def create_with_artifacts(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a result with artifacts."""
        return cls.create(
            artifacts=kwargs.pop("artifacts", [
                {
                    "name": "model_weights.pt",
                    "type": "model",
                    "size_bytes": 1024 * 1024 * 100,  # 100MB
                    "path": "s3://experiments/results/model_weights.pt",
                },
                {
                    "name": "training_logs.json",
                    "type": "logs",
                    "size_bytes": 1024 * 10,  # 10KB
                    "path": "s3://experiments/results/training_logs.json",
                },
                {
                    "name": "evaluation_report.pdf",
                    "type": "report",
                    "size_bytes": 1024 * 50,  # 50KB
                    "path": "s3://experiments/results/evaluation_report.pdf",
                },
            ]),
            **kwargs,
        )


@dataclass
class HypothesisFactory:
    """Factory for creating Hypothesis test instances."""

    _counter: int = field(default=0, repr=False)

    @classmethod
    def create(
        cls,
        hypothesis_id: str | None = None,
        title: str | None = None,
        description: str | None = None,
        domain: str = "ml_ai",
        status: str = "proposed",
        confidence: float = 0.7,
        created_by: str | None = None,
        supporting_evidence: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a hypothesis data dictionary."""
        cls._counter = getattr(cls, "_counter", 0) + 1

        return {
            "hypothesis_id": hypothesis_id or str(uuid4()),
            "title": title or f"Test Hypothesis {cls._counter}",
            "description": description or f"Description for test hypothesis {cls._counter}",
            "domain": domain,
            "status": status,
            "confidence": confidence,
            "created_by": created_by or str(uuid4()),
            "supporting_evidence": supporting_evidence or [],
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
            **kwargs,
        }

    @classmethod
    def create_verified(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a verified hypothesis."""
        return cls.create(
            status="verified",
            confidence=kwargs.pop("confidence", 0.95),
            supporting_evidence=kwargs.pop("supporting_evidence", [
                {"type": "experiment", "id": str(uuid4()), "result": "positive"},
            ]),
            **kwargs,
        )

    @classmethod
    def create_refuted(cls, **kwargs: Any) -> dict[str, Any]:
        """Create a refuted hypothesis."""
        return cls.create(
            status="refuted",
            confidence=kwargs.pop("confidence", 0.1),
            **kwargs,
        )

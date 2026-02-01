"""Configuration for ML/AI verification engine."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class MLVerifierSettings(BaseSettings):
    """Settings for ML verification engine."""

    model_config = {"env_prefix": "ML_VERIFIER_", "case_sensitive": False}

    # Git settings
    git_clone_timeout_seconds: int = Field(default=300, description="Timeout for git clone")
    max_repo_size_mb: int = Field(default=5000, description="Maximum repo size to clone")
    allowed_git_hosts: list[str] = Field(
        default=["github.com", "gitlab.com", "huggingface.co"],
        description="Allowed git hosts",
    )

    # Environment settings
    docker_enabled: bool = Field(default=True, description="Enable Docker environments")
    nix_enabled: bool = Field(default=True, description="Enable Nix flake environments")
    max_build_time_seconds: int = Field(default=1800, description="Max env build time")
    container_registry: str = Field(
        default="ghcr.io/autonomous-research",
        description="Container registry for base images",
    )

    # Execution settings
    default_timeout_seconds: int = Field(default=3600, description="Default job timeout")
    max_timeout_seconds: int = Field(default=86400, description="Maximum job timeout")
    max_gpu_hours: float = Field(default=24.0, description="Max GPU hours per verification")
    max_memory_gb: int = Field(default=64, description="Max memory per job")

    # Kubernetes settings
    k8s_namespace: str = Field(default="ml-verification", description="K8s namespace")
    k8s_service_account: str = Field(default="ml-verifier", description="K8s service account")
    gpu_node_selector: dict[str, str] = Field(
        default={"gpu": "true"},
        description="Node selector for GPU jobs",
    )

    # Modal settings (alternative compute)
    modal_enabled: bool = Field(default=False, description="Enable Modal.com compute")
    modal_token_secret: str = Field(default="modal-token", description="K8s secret for Modal token")

    # Dataset settings
    dataset_cache_path: str = Field(
        default="/data/datasets",
        description="Path to cached datasets",
    )
    huggingface_cache_path: str = Field(
        default="/data/hf_cache",
        description="HuggingFace cache path",
    )
    max_dataset_size_gb: float = Field(default=100.0, description="Max dataset size")

    # Benchmark settings
    lm_eval_harness_path: str = Field(
        default="/opt/lm-evaluation-harness",
        description="Path to lm-evaluation-harness",
    )
    helm_path: str = Field(default="/opt/helm", description="Path to HELM")

    # Metric comparison settings
    default_tolerance_percent: float = Field(
        default=1.0,
        description="Default tolerance for metric comparison (%)",
    )
    strict_tolerance_percent: float = Field(
        default=0.1,
        description="Strict tolerance for key metrics (%)",
    )

    # Novelty checking
    papers_with_code_enabled: bool = Field(
        default=True,
        description="Enable Papers With Code integration",
    )
    semantic_scholar_api_key: str | None = Field(
        default=None,
        description="Semantic Scholar API key",
    )

    # Resource limits
    max_concurrent_jobs: int = Field(default=10, description="Max concurrent jobs")
    job_queue_size: int = Field(default=100, description="Max queued jobs")


@lru_cache
def get_settings() -> MLVerifierSettings:
    """Get cached ML verifier settings."""
    return MLVerifierSettings()


# Supported experiment types
EXPERIMENT_TYPES = {
    "training": {
        "name": "Model Training",
        "description": "Full model training reproducibility",
        "requires_gpu": True,
    },
    "fine_tuning": {
        "name": "Fine-tuning",
        "description": "Model fine-tuning on specific task",
        "requires_gpu": True,
    },
    "inference": {
        "name": "Inference/Evaluation",
        "description": "Model inference and evaluation only",
        "requires_gpu": True,
    },
    "benchmark": {
        "name": "Benchmark Evaluation",
        "description": "Standardized benchmark evaluation",
        "requires_gpu": True,
    },
}

# Supported frameworks
ML_FRAMEWORKS = {
    "pytorch": {
        "name": "PyTorch",
        "base_image": "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime",
        "setup_commands": ["pip install torch torchvision torchaudio"],
    },
    "tensorflow": {
        "name": "TensorFlow",
        "base_image": "tensorflow/tensorflow:2.15.0-gpu",
        "setup_commands": ["pip install tensorflow"],
    },
    "jax": {
        "name": "JAX",
        "base_image": "ghcr.io/google/jax:jax-0.4.23-cuda12",
        "setup_commands": ["pip install jax jaxlib"],
    },
    "transformers": {
        "name": "HuggingFace Transformers",
        "base_image": "huggingface/transformers-pytorch-gpu:latest",
        "setup_commands": ["pip install transformers datasets accelerate"],
    },
}

# Supported hardware configurations
GPU_CONFIGS = {
    "a100_40gb": {
        "name": "NVIDIA A100 40GB",
        "memory_gb": 40,
        "cuda_compute": "8.0",
    },
    "a100_80gb": {
        "name": "NVIDIA A100 80GB",
        "memory_gb": 80,
        "cuda_compute": "8.0",
    },
    "h100_80gb": {
        "name": "NVIDIA H100 80GB",
        "memory_gb": 80,
        "cuda_compute": "9.0",
    },
    "v100_16gb": {
        "name": "NVIDIA V100 16GB",
        "memory_gb": 16,
        "cuda_compute": "7.0",
    },
    "rtx4090": {
        "name": "NVIDIA RTX 4090 24GB",
        "memory_gb": 24,
        "cuda_compute": "8.9",
    },
}

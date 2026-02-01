"""Configuration for the Mathematics Verification Engine."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Math Verifier settings."""

    # Service info
    service_name: str = "math-verifier"
    service_version: str = "0.1.0"

    # Lean 4 settings
    lean_executable: str = "lake"
    lean_timeout_seconds: int = 300  # 5 minutes for proof compilation
    lean_memory_limit_mb: int = 8192  # 8 GB
    mathlib_path: str = "/opt/mathlib4"

    # SMT solver settings
    z3_executable: str = "z3"
    z3_timeout_seconds: int = 60
    cvc5_executable: str = "cvc5"
    cvc5_timeout_seconds: int = 60

    # Container settings
    use_singularity: bool = True
    singularity_image: str = "/opt/containers/math-verifier.sif"
    sandbox_enabled: bool = True

    # Novelty checking
    mathlib_index_path: str = "/opt/mathlib4/index"
    novelty_check_enabled: bool = True
    similarity_threshold: float = 0.85

    # Proof metrics
    max_proof_lines: int = 10000
    max_axioms: int = 50

    # Redis for caching
    redis_url: str = "redis://localhost:6379/0"

    # Temporary directory for proof files
    temp_dir: str = "/tmp/math-verifier"

    # Logging
    log_level: str = "INFO"
    log_json: bool = True

    class Config:
        env_file = ".env"
        env_prefix = "MATH_VERIFIER_"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Supported proof systems
PROOF_SYSTEMS = {
    "lean4": {
        "name": "Lean 4",
        "file_extension": ".lean",
        "executor": "lean4",
        "description": "Interactive theorem prover with dependent types",
    },
    "coq": {
        "name": "Coq",
        "file_extension": ".v",
        "executor": "coq",
        "description": "Formal proof management system",
    },
    "isabelle": {
        "name": "Isabelle/HOL",
        "file_extension": ".thy",
        "executor": "isabelle",
        "description": "Generic proof assistant",
    },
    "agda": {
        "name": "Agda",
        "file_extension": ".agda",
        "executor": "agda",
        "description": "Dependently typed programming language",
    },
    "z3": {
        "name": "Z3",
        "file_extension": ".smt2",
        "executor": "smt",
        "description": "SMT solver for automated reasoning",
    },
    "cvc5": {
        "name": "CVC5",
        "file_extension": ".smt2",
        "executor": "smt",
        "description": "SMT solver for automated reasoning",
    },
}

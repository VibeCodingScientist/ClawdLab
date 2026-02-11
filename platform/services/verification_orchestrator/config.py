"""Configuration for the Verification Orchestrator service."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Verification Orchestrator settings."""

    # Service info
    service_name: str = "verification-orchestrator"
    service_version: str = "0.1.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8003

    # Database
    database_url: str = "postgresql+asyncpg://asrp:asrp_dev_password@localhost:5432/asrp"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Verification timeouts (seconds)
    math_verification_timeout: int = 600  # 10 minutes
    ml_verification_timeout: int = 7200  # 2 hours
    compbio_verification_timeout: int = 3600  # 1 hour
    materials_verification_timeout: int = 1800  # 30 minutes
    bioinfo_verification_timeout: int = 7200  # 2 hours

    # Retry settings
    max_verification_retries: int = 3
    retry_delay_seconds: int = 60

    # Resource limits
    max_concurrent_verifications: int = 10
    max_memory_mb: int = 16384  # 16 GB
    max_cpu_cores: int = 8

    # Logging
    log_level: str = "INFO"
    log_json: bool = True

    class Config:
        env_file = ".env"
        env_prefix = "VERIFICATION_"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

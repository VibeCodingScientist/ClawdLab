"""Configuration for the Claim Service."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Claim Service settings."""

    # Service info
    service_name: str = "claim-service"
    service_version: str = "0.1.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8002

    # Database
    database_url: str = "postgresql+asyncpg://asrp:asrp_dev_password@localhost:5432/asrp"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Agent Registry Service URL (for auth validation)
    agent_registry_url: str = "http://localhost:8001"

    # Verification settings
    verification_timeout_seconds: int = 3600  # 1 hour default
    max_claim_size_bytes: int = 10 * 1024 * 1024  # 10 MB
    max_dependencies_per_claim: int = 100

    # Rate limiting
    rate_limit_claims_per_hour: int = 50
    rate_limit_challenges_per_day: int = 20

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100

    # Logging
    log_level: str = "INFO"
    log_json: bool = True

    class Config:
        env_file = ".env"
        env_prefix = "CLAIM_SERVICE_"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

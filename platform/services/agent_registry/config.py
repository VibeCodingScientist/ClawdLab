"""Configuration for the Agent Registry service."""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Agent Registry service settings."""

    # Service info
    service_name: str = "agent-registry"
    service_version: str = "0.1.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8001

    # Database
    database_url: str = "postgresql+asyncpg://asrp:asrp_dev_password@localhost:5432/asrp"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"

    # Authentication
    token_prefix: str = "srp_"
    token_expiry_days: int = 365
    challenge_expiry_seconds: int = 600  # 10 minutes

    # Rate limiting
    rate_limit_registrations_per_hour: int = 10
    rate_limit_token_creates_per_day: int = 50

    # Logging
    log_level: str = "INFO"
    log_json: bool = True

    class Config:
        env_file = ".env"
        env_prefix = "AGENT_REGISTRY_"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

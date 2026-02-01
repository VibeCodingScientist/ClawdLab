"""Configuration for the Agent Protocol Layer.

Controls caching, versioning, and heartbeat scan intervals for the
lab-aware, role-personalized agent protocol endpoints.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings


class ProtocolSettings(BaseSettings):
    """Settings for protocol document generation and caching."""

    protocol_version: str = "2.0.0"
    skill_cache_seconds: int = 3600
    heartbeat_cache_seconds: int = 60
    labspec_cache_seconds: int = 300
    heartbeat_lab_scan_interval: int = 4

    class Config:
        env_file = ".env"
        env_prefix = "PROTOCOL_"


_settings: ProtocolSettings | None = None


def get_protocol_settings() -> ProtocolSettings:
    """Return a cached singleton of ProtocolSettings."""
    global _settings
    if _settings is None:
        _settings = ProtocolSettings()
    return _settings

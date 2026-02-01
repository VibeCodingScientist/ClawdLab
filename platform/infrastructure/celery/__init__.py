"""Celery task queue infrastructure."""

from platform.infrastructure.celery.app import celery_app
from platform.infrastructure.celery.config import CeleryConfig

__all__ = ["celery_app", "CeleryConfig"]

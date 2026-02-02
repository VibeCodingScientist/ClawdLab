"""Autonomous Scientific Research Platform.

A comprehensive platform where AI agents autonomously conduct scientific research
with automated computational verification.

Modules:
    - agents: Agent communication and coordination
    - experiments: Experiment planning and scheduling
    - knowledge: Knowledge graph and vector database
    - literature: Literature search and integration
    - monitoring: Metrics, health checks, and alerting
    - orchestration: Research workflow management
    - reporting: Reports, visualizations, and dashboards
    - security: Authentication, authorization, and audit
"""

from platform.main import app, create_app, APP_VERSION, APP_TITLE

__version__ = APP_VERSION
__all__ = ["app", "create_app", "APP_VERSION", "APP_TITLE"]

"""Configuration for Monitoring and Observability."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class MonitoringSettings(BaseSettings):
    """Settings for monitoring and observability."""

    model_config = {"env_prefix": "MONITORING_", "case_sensitive": False}

    # Metrics Settings
    metrics_enabled: bool = Field(
        default=True,
        description="Enable metrics collection",
    )
    metrics_retention_hours: int = Field(
        default=168,  # 1 week
        description="Hours to retain metrics data",
    )
    metrics_flush_interval_seconds: int = Field(
        default=10,
        description="Interval to flush metrics",
    )
    max_metrics_per_service: int = Field(
        default=1000,
        description="Maximum metrics per service",
    )

    # Health Check Settings
    health_check_enabled: bool = Field(
        default=True,
        description="Enable health checks",
    )
    health_check_interval_seconds: int = Field(
        default=30,
        description="Health check interval",
    )
    health_check_timeout_seconds: int = Field(
        default=10,
        description="Health check timeout",
    )
    unhealthy_threshold: int = Field(
        default=3,
        description="Consecutive failures before unhealthy",
    )
    healthy_threshold: int = Field(
        default=2,
        description="Consecutive successes before healthy",
    )

    # Alerting Settings
    alerting_enabled: bool = Field(
        default=True,
        description="Enable alerting",
    )
    alert_evaluation_interval_seconds: int = Field(
        default=60,
        description="Alert rule evaluation interval",
    )
    alert_retention_days: int = Field(
        default=30,
        description="Days to retain alert history",
    )
    max_alerts_per_rule: int = Field(
        default=100,
        description="Maximum alerts per rule",
    )

    # Logging Settings
    log_level: str = Field(
        default="INFO",
        description="Default log level",
    )
    log_retention_days: int = Field(
        default=7,
        description="Days to retain logs",
    )
    max_log_entries: int = Field(
        default=100000,
        description="Maximum log entries in memory",
    )
    structured_logging: bool = Field(
        default=True,
        description="Use structured JSON logging",
    )

    # Tracing Settings
    tracing_enabled: bool = Field(
        default=True,
        description="Enable distributed tracing",
    )
    trace_sample_rate: float = Field(
        default=0.1,
        description="Trace sampling rate (0.0-1.0)",
    )
    trace_retention_hours: int = Field(
        default=24,
        description="Hours to retain traces",
    )
    max_spans_per_trace: int = Field(
        default=1000,
        description="Maximum spans per trace",
    )


@lru_cache
def get_settings() -> MonitoringSettings:
    """Get cached monitoring settings."""
    return MonitoringSettings()


# Metric Types
METRIC_TYPES = {
    "counter": {
        "name": "Counter",
        "description": "Monotonically increasing value",
        "operations": ["increment", "get"],
    },
    "gauge": {
        "name": "Gauge",
        "description": "Value that can go up or down",
        "operations": ["set", "increment", "decrement", "get"],
    },
    "histogram": {
        "name": "Histogram",
        "description": "Distribution of values",
        "operations": ["observe", "get_percentile", "get_mean"],
    },
    "timer": {
        "name": "Timer",
        "description": "Duration measurements",
        "operations": ["start", "stop", "record", "get_mean"],
    },
    "summary": {
        "name": "Summary",
        "description": "Pre-calculated quantiles",
        "operations": ["observe", "get_quantile"],
    },
}

# Health Status
HEALTH_STATUSES = {
    "healthy": {
        "name": "Healthy",
        "description": "Service is operating normally",
        "color": "green",
    },
    "degraded": {
        "name": "Degraded",
        "description": "Service is partially impaired",
        "color": "yellow",
    },
    "unhealthy": {
        "name": "Unhealthy",
        "description": "Service is not functioning",
        "color": "red",
    },
    "unknown": {
        "name": "Unknown",
        "description": "Health status cannot be determined",
        "color": "gray",
    },
}

# Alert Severities
ALERT_SEVERITIES = {
    "critical": {
        "name": "Critical",
        "description": "Immediate action required",
        "priority": 1,
        "color": "red",
    },
    "warning": {
        "name": "Warning",
        "description": "Attention needed soon",
        "priority": 2,
        "color": "orange",
    },
    "info": {
        "name": "Info",
        "description": "Informational alert",
        "priority": 3,
        "color": "blue",
    },
}

# Alert States
ALERT_STATES = {
    "pending": "Alert condition detected, waiting for threshold",
    "firing": "Alert is actively firing",
    "resolved": "Alert condition has been resolved",
    "acknowledged": "Alert has been acknowledged by operator",
    "silenced": "Alert is silenced",
}

# Log Levels
LOG_LEVELS = {
    "DEBUG": {"value": 10, "color": "gray"},
    "INFO": {"value": 20, "color": "blue"},
    "WARNING": {"value": 30, "color": "yellow"},
    "ERROR": {"value": 40, "color": "red"},
    "CRITICAL": {"value": 50, "color": "purple"},
}

# Standard Metrics
STANDARD_METRICS = {
    "requests_total": {
        "type": "counter",
        "description": "Total number of requests",
        "labels": ["service", "method", "status"],
    },
    "request_duration_seconds": {
        "type": "histogram",
        "description": "Request duration in seconds",
        "labels": ["service", "method"],
        "buckets": [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    },
    "active_connections": {
        "type": "gauge",
        "description": "Number of active connections",
        "labels": ["service"],
    },
    "errors_total": {
        "type": "counter",
        "description": "Total number of errors",
        "labels": ["service", "error_type"],
    },
    "memory_usage_bytes": {
        "type": "gauge",
        "description": "Memory usage in bytes",
        "labels": ["service"],
    },
    "cpu_usage_percent": {
        "type": "gauge",
        "description": "CPU usage percentage",
        "labels": ["service"],
    },
    "queue_depth": {
        "type": "gauge",
        "description": "Number of items in queue",
        "labels": ["queue_name"],
    },
    "task_duration_seconds": {
        "type": "timer",
        "description": "Task execution duration",
        "labels": ["task_type"],
    },
}

# Health Check Types
HEALTH_CHECK_TYPES = {
    "http": {
        "name": "HTTP Check",
        "description": "Check HTTP endpoint availability",
    },
    "tcp": {
        "name": "TCP Check",
        "description": "Check TCP port availability",
    },
    "database": {
        "name": "Database Check",
        "description": "Check database connectivity",
    },
    "custom": {
        "name": "Custom Check",
        "description": "Custom health check function",
    },
    "dependency": {
        "name": "Dependency Check",
        "description": "Check dependent service health",
    },
}

# Services to Monitor
MONITORED_SERVICES = [
    "api_gateway",
    "knowledge_service",
    "agent_service",
    "literature_service",
    "experiment_service",
    "reporting_service",
    "orchestration_service",
    "verification_service",
    "database",
    "cache",
    "message_queue",
]

# Dashboard Metrics
DASHBOARD_METRICS = {
    "system_overview": [
        "requests_total",
        "errors_total",
        "active_connections",
        "memory_usage_bytes",
        "cpu_usage_percent",
    ],
    "experiment_metrics": [
        "experiments_running",
        "experiments_completed",
        "experiments_failed",
        "gpu_utilization",
        "experiment_duration",
    ],
    "agent_metrics": [
        "agents_active",
        "messages_processed",
        "message_queue_depth",
        "agent_response_time",
    ],
}

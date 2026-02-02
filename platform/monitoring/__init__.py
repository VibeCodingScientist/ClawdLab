"""Monitoring and Observability Module.

This module provides comprehensive monitoring and observability capabilities:
- Metrics collection with counters, gauges, histograms, and timers
- Health checks with liveness/readiness probes
- Alerting system with rules, silences, and notifications
- Structured logging
- Distributed tracing

The monitoring layer enables tracking system health, performance,
and operational status across all platform services.
"""

from platform.monitoring.alerts import (
    AlertManager,
    get_alert_manager,
)
from platform.monitoring.base import (
    # Enums
    AlertSeverity,
    AlertState,
    HealthStatus,
    LogLevel,
    MetricType,
    # Metric classes
    HistogramBucket,
    HistogramValue,
    Metric,
    MetricLabel,
    MetricValue,
    # Health check classes
    HealthCheck,
    HealthCheckResult,
    ServiceHealth,
    # Alert classes
    Alert,
    AlertCondition,
    AlertRule,
    # Logging classes
    LogEntry,
    # Tracing classes
    Span,
    SpanContext,
    SpanEvent,
    Trace,
    # Status classes
    SystemStatus,
)
from platform.monitoring.config import (
    ALERT_SEVERITIES,
    ALERT_STATES,
    DASHBOARD_METRICS,
    HEALTH_CHECK_TYPES,
    HEALTH_STATUSES,
    LOG_LEVELS,
    METRIC_TYPES,
    MONITORED_SERVICES,
    STANDARD_METRICS,
    MonitoringSettings,
    get_settings,
)
from platform.monitoring.health import (
    HealthCheckService,
    get_health_service,
)
from platform.monitoring.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsCollector,
    Timer,
    get_metrics_collector,
)
from platform.monitoring.service import (
    MonitoringService,
    MonitoringStats,
    get_monitoring_service,
)

__all__ = [
    # Config
    "get_settings",
    "MonitoringSettings",
    "METRIC_TYPES",
    "HEALTH_STATUSES",
    "ALERT_SEVERITIES",
    "ALERT_STATES",
    "LOG_LEVELS",
    "STANDARD_METRICS",
    "HEALTH_CHECK_TYPES",
    "MONITORED_SERVICES",
    "DASHBOARD_METRICS",
    # Enums
    "MetricType",
    "HealthStatus",
    "AlertSeverity",
    "AlertState",
    "LogLevel",
    # Metric classes
    "MetricLabel",
    "MetricValue",
    "Metric",
    "HistogramBucket",
    "HistogramValue",
    # Health check classes
    "HealthCheckResult",
    "HealthCheck",
    "ServiceHealth",
    # Alert classes
    "AlertCondition",
    "AlertRule",
    "Alert",
    # Logging classes
    "LogEntry",
    # Tracing classes
    "SpanContext",
    "SpanEvent",
    "Span",
    "Trace",
    # Status classes
    "SystemStatus",
    # Metric types
    "Counter",
    "Gauge",
    "Histogram",
    "Timer",
    # Collectors and services
    "MetricsCollector",
    "get_metrics_collector",
    "HealthCheckService",
    "get_health_service",
    "AlertManager",
    "get_alert_manager",
    # Main service
    "MonitoringService",
    "MonitoringStats",
    "get_monitoring_service",
]

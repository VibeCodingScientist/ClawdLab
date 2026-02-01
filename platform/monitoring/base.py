"""Base classes and data structures for Monitoring and Observability."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable
from uuid import uuid4


class MetricType(Enum):
    """Type of metric."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    SUMMARY = "summary"


class HealthStatus(Enum):
    """Health status of a service."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class AlertSeverity(Enum):
    """Severity level of an alert."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertState(Enum):
    """State of an alert."""

    PENDING = "pending"
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"
    SILENCED = "silenced"


class LogLevel(Enum):
    """Log level."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ===========================================
# METRIC DATA CLASSES
# ===========================================


@dataclass
class MetricLabel:
    """A label for a metric."""

    name: str = ""
    value: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "value": self.value}


@dataclass
class MetricValue:
    """A timestamped metric value."""

    value: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    labels: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "labels": self.labels,
        }


@dataclass
class Metric:
    """A metric definition and its values."""

    metric_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    metric_type: MetricType = MetricType.GAUGE
    unit: str = ""
    labels: list[str] = field(default_factory=list)
    values: list[MetricValue] = field(default_factory=list)
    buckets: list[float] = field(default_factory=list)  # For histograms
    current_value: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "description": self.description,
            "metric_type": self.metric_type.value,
            "unit": self.unit,
            "labels": self.labels,
            "current_value": self.current_value,
            "values_count": len(self.values),
            "buckets": self.buckets,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class HistogramBucket:
    """A histogram bucket."""

    le: float = 0.0  # Less than or equal
    count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"le": self.le, "count": self.count}


@dataclass
class HistogramValue:
    """A histogram value with buckets."""

    buckets: list[HistogramBucket] = field(default_factory=list)
    sum: float = 0.0
    count: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "buckets": [b.to_dict() for b in self.buckets],
            "sum": self.sum,
            "count": self.count,
            "timestamp": self.timestamp.isoformat(),
        }


# ===========================================
# HEALTH CHECK DATA CLASSES
# ===========================================


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    status: HealthStatus = HealthStatus.UNKNOWN
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class HealthCheck:
    """A health check definition."""

    check_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    check_type: str = "custom"  # http, tcp, database, custom, dependency
    target: str = ""  # URL, host:port, or service name
    interval_seconds: int = 30
    timeout_seconds: int = 10
    enabled: bool = True
    check_fn: Callable[[], HealthCheckResult] | None = None
    last_result: HealthCheckResult | None = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "description": self.description,
            "check_type": self.check_type,
            "target": self.target,
            "interval_seconds": self.interval_seconds,
            "timeout_seconds": self.timeout_seconds,
            "enabled": self.enabled,
            "last_result": self.last_result.to_dict() if self.last_result else None,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ServiceHealth:
    """Health status of a service."""

    service_id: str = field(default_factory=lambda: str(uuid4()))
    service_name: str = ""
    status: HealthStatus = HealthStatus.UNKNOWN
    checks: list[HealthCheck] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    last_check: datetime | None = None
    uptime_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "service_id": self.service_id,
            "service_name": self.service_name,
            "status": self.status.value,
            "checks": [c.to_dict() for c in self.checks],
            "dependencies": self.dependencies,
            "metadata": self.metadata,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "uptime_seconds": self.uptime_seconds,
        }


# ===========================================
# ALERT DATA CLASSES
# ===========================================


@dataclass
class AlertCondition:
    """Condition that triggers an alert."""

    metric_name: str = ""
    operator: str = ">"  # >, <, >=, <=, ==, !=
    threshold: float = 0.0
    duration_seconds: int = 0  # How long condition must be true
    labels: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "operator": self.operator,
            "threshold": self.threshold,
            "duration_seconds": self.duration_seconds,
            "labels": self.labels,
        }


@dataclass
class AlertRule:
    """A rule that defines when to trigger an alert."""

    rule_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    severity: AlertSeverity = AlertSeverity.WARNING
    condition: AlertCondition = field(default_factory=AlertCondition)
    enabled: bool = True
    annotations: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "severity": self.severity.value,
            "condition": self.condition.to_dict(),
            "enabled": self.enabled,
            "annotations": self.annotations,
            "labels": self.labels,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Alert:
    """An active alert instance."""

    alert_id: str = field(default_factory=lambda: str(uuid4()))
    rule_id: str = ""
    name: str = ""
    severity: AlertSeverity = AlertSeverity.WARNING
    state: AlertState = AlertState.PENDING
    message: str = ""
    value: float = 0.0
    threshold: float = 0.0
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "rule_id": self.rule_id,
            "name": self.name,
            "severity": self.severity.value,
            "state": self.state.value,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "labels": self.labels,
            "annotations": self.annotations,
            "started_at": self.started_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
        }


# ===========================================
# LOGGING DATA CLASSES
# ===========================================


@dataclass
class LogEntry:
    """A log entry."""

    entry_id: str = field(default_factory=lambda: str(uuid4()))
    level: LogLevel = LogLevel.INFO
    message: str = ""
    logger: str = ""
    service: str = ""
    trace_id: str = ""
    span_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    context: dict[str, Any] = field(default_factory=dict)
    exception: str | None = None
    stack_trace: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "level": self.level.value,
            "message": self.message,
            "logger": self.logger,
            "service": self.service,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context,
            "exception": self.exception,
            "stack_trace": self.stack_trace,
        }


# ===========================================
# TRACING DATA CLASSES
# ===========================================


@dataclass
class SpanContext:
    """Context for distributed tracing."""

    trace_id: str = ""
    span_id: str = ""
    parent_span_id: str = ""
    sampled: bool = True
    baggage: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "sampled": self.sampled,
            "baggage": self.baggage,
        }


@dataclass
class SpanEvent:
    """An event within a span."""

    name: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "timestamp": self.timestamp.isoformat(),
            "attributes": self.attributes,
        }


@dataclass
class Span:
    """A span in a distributed trace."""

    span_id: str = field(default_factory=lambda: str(uuid4())[:16])
    trace_id: str = ""
    parent_span_id: str = ""
    name: str = ""
    service: str = ""
    operation: str = ""
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime | None = None
    duration_ms: float = 0.0
    status: str = "ok"  # ok, error
    status_message: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[SpanEvent] = field(default_factory=list)
    links: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "service": self.service,
            "operation": self.operation,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "status_message": self.status_message,
            "attributes": self.attributes,
            "events": [e.to_dict() for e in self.events],
            "links": self.links,
        }


@dataclass
class Trace:
    """A distributed trace."""

    trace_id: str = field(default_factory=lambda: str(uuid4())[:32])
    root_span_id: str = ""
    service: str = ""
    operation: str = ""
    spans: list[Span] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: datetime | None = None
    duration_ms: float = 0.0
    status: str = "ok"
    tags: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "root_span_id": self.root_span_id,
            "service": self.service,
            "operation": self.operation,
            "spans": [s.to_dict() for s in self.spans],
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "tags": self.tags,
        }


# ===========================================
# SYSTEM STATUS DATA CLASSES
# ===========================================


@dataclass
class SystemStatus:
    """Overall system status."""

    status: HealthStatus = HealthStatus.UNKNOWN
    services: list[ServiceHealth] = field(default_factory=list)
    active_alerts: int = 0
    total_requests: int = 0
    error_rate: float = 0.0
    avg_response_time_ms: float = 0.0
    uptime_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "services": [s.to_dict() for s in self.services],
            "active_alerts": self.active_alerts,
            "total_requests": self.total_requests,
            "error_rate": self.error_rate,
            "avg_response_time_ms": self.avg_response_time_ms,
            "uptime_seconds": self.uptime_seconds,
            "timestamp": self.timestamp.isoformat(),
        }


__all__ = [
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
]

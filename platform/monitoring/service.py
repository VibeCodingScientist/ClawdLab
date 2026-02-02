"""Main Monitoring Service."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from platform.monitoring.alerts import AlertManager, get_alert_manager
from platform.monitoring.base import (
    Alert,
    AlertRule,
    AlertSeverity,
    HealthCheck,
    HealthCheckResult,
    HealthStatus,
    LogEntry,
    LogLevel,
    Metric,
    ServiceHealth,
    Span,
    SystemStatus,
    Trace,
)
from platform.monitoring.config import get_settings
from platform.monitoring.health import HealthCheckService, get_health_service
from platform.monitoring.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsCollector,
    Timer,
    get_metrics_collector,
)


@dataclass
class MonitoringStats:
    """Statistics about monitoring system."""

    total_metrics: int = 0
    total_counters: int = 0
    total_gauges: int = 0
    total_histograms: int = 0
    total_timers: int = 0
    total_health_checks: int = 0
    healthy_services: int = 0
    unhealthy_services: int = 0
    total_alert_rules: int = 0
    active_alerts: int = 0
    total_log_entries: int = 0
    total_traces: int = 0
    uptime_seconds: float = 0.0


class MonitoringService:
    """Main service for monitoring and observability."""

    def __init__(
        self,
        metrics_collector: MetricsCollector | None = None,
        health_service: HealthCheckService | None = None,
        alert_manager: AlertManager | None = None,
    ) -> None:
        self._settings = get_settings()
        self._metrics = metrics_collector or get_metrics_collector()
        self._health = health_service or get_health_service()
        self._alerts = alert_manager or get_alert_manager()

        # Logging storage
        self._log_entries: list[LogEntry] = []
        self._log_handlers: list[Callable[[LogEntry], None]] = []

        # Tracing storage
        self._traces: dict[str, Trace] = {}
        self._active_spans: dict[str, Span] = {}

        self._start_time = datetime.utcnow()

    # ===========================================
    # LIFECYCLE
    # ===========================================

    async def start(self) -> None:
        """Start the monitoring service."""
        await self._health.start()
        await self._alerts.start()

    async def stop(self) -> None:
        """Stop the monitoring service."""
        await self._health.stop()
        await self._alerts.stop()

    # ===========================================
    # METRICS
    # ===========================================

    def create_counter(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
    ) -> Counter:
        """Create a counter metric."""
        return self._metrics.create_counter(name, description, labels)

    def create_gauge(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
    ) -> Gauge:
        """Create a gauge metric."""
        return self._metrics.create_gauge(name, description, labels)

    def create_histogram(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
        buckets: list[float] | None = None,
    ) -> Histogram:
        """Create a histogram metric."""
        return self._metrics.create_histogram(name, description, labels, buckets)

    def create_timer(
        self,
        name: str,
        description: str = "",
        labels: list[str] | None = None,
    ) -> Timer:
        """Create a timer metric."""
        return self._metrics.create_timer(name, description, labels)

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        """Increment a counter or gauge."""
        self._metrics.increment(name, value, **labels)

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        """Set a gauge value."""
        self._metrics.set_gauge(name, value, **labels)

    def observe(self, name: str, value: float, **labels: str) -> None:
        """Observe a value for a histogram."""
        self._metrics.observe(name, value, **labels)

    def record_time(self, name: str, duration: float, **labels: str) -> None:
        """Record a duration for a timer."""
        self._metrics.record_time(name, duration, **labels)

    def get_metric(self, name: str) -> Metric | None:
        """Get a metric by name."""
        return self._metrics.get_metric(name)

    def get_metric_value(self, name: str, **labels: str) -> float | None:
        """Get the current value of a metric."""
        return self._metrics.get_metric_value(name, **labels)

    def get_all_metrics(self) -> list[Metric]:
        """Get all registered metrics."""
        return self._metrics.get_all_metrics()

    def collect_metrics(self) -> dict[str, Any]:
        """Collect all current metric values."""
        return self._metrics.collect()

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        return self._metrics.export_prometheus()

    # ===========================================
    # HEALTH CHECKS
    # ===========================================

    def register_health_check(
        self,
        name: str,
        check_fn: Callable[[], HealthCheckResult],
        service: str = "",
        check_type: str = "custom",
    ) -> HealthCheck:
        """Register a health check."""
        return self._health.register_check(
            name=name,
            check_fn=check_fn,
            check_type=check_type,
            service=service,
        )

    def register_http_check(
        self,
        name: str,
        url: str,
        service: str = "",
    ) -> HealthCheck:
        """Register an HTTP health check."""
        return self._health.register_http_check(name, url, service)

    def register_tcp_check(
        self,
        name: str,
        host: str,
        port: int,
        service: str = "",
    ) -> HealthCheck:
        """Register a TCP health check."""
        return self._health.register_tcp_check(name, host, port, service)

    async def run_health_checks(self) -> dict[str, HealthCheckResult]:
        """Run all health checks."""
        return await self._health.run_all_checks()

    async def liveness(self) -> HealthCheckResult:
        """Check service liveness."""
        return await self._health.liveness()

    async def readiness(self) -> HealthCheckResult:
        """Check service readiness."""
        return await self._health.readiness()

    def get_service_health(self, service_name: str) -> ServiceHealth | None:
        """Get health status for a service."""
        return self._health.get_service(service_name)

    def get_all_services(self) -> list[ServiceHealth]:
        """Get health status for all services."""
        return self._health.get_all_services()

    def get_overall_health(self) -> HealthStatus:
        """Get overall system health status."""
        return self._health.get_overall_status()

    def get_health_summary(self) -> dict[str, Any]:
        """Get health check summary."""
        return self._health.get_summary()

    # ===========================================
    # ALERTING
    # ===========================================

    def create_alert_rule(
        self,
        name: str,
        metric_name: str,
        operator: str,
        threshold: float,
        severity: AlertSeverity = AlertSeverity.WARNING,
        duration_seconds: int = 0,
        description: str = "",
    ) -> AlertRule:
        """Create an alert rule."""
        return self._alerts.create_rule(
            name=name,
            metric_name=metric_name,
            operator_str=operator,
            threshold=threshold,
            severity=severity,
            duration_seconds=duration_seconds,
            description=description,
        )

    def get_alert_rule(self, rule_id: str) -> AlertRule | None:
        """Get an alert rule by ID."""
        return self._alerts.get_rule(rule_id)

    def get_all_rules(self) -> list[AlertRule]:
        """Get all alert rules."""
        return self._alerts.get_all_rules()

    def delete_alert_rule(self, rule_id: str) -> bool:
        """Delete an alert rule."""
        return self._alerts.delete_rule(rule_id)

    def get_active_alerts(self) -> list[Alert]:
        """Get all active alerts."""
        return self._alerts.get_active_alerts()

    def get_alert(self, alert_id: str) -> Alert | None:
        """Get an alert by ID."""
        return self._alerts.get_alert(alert_id)

    def get_alert_history(
        self,
        limit: int = 100,
        severity: AlertSeverity | None = None,
    ) -> list[Alert]:
        """Get alert history."""
        return self._alerts.get_alert_history(limit=limit, severity=severity)

    async def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str,
    ) -> Alert | None:
        """Acknowledge an alert."""
        return await self._alerts.acknowledge_alert(alert_id, acknowledged_by)

    async def resolve_alert(self, alert_id: str) -> Alert | None:
        """Resolve an alert."""
        return await self._alerts.resolve_alert(alert_id)

    def create_silence(
        self,
        matchers: dict[str, str],
        duration_seconds: int,
        created_by: str,
        comment: str = "",
    ) -> str:
        """Create a silence."""
        return self._alerts.create_silence(matchers, duration_seconds, created_by, comment)

    def get_alert_stats(self) -> dict[str, Any]:
        """Get alerting statistics."""
        return self._alerts.get_stats()

    # ===========================================
    # LOGGING
    # ===========================================

    def log(
        self,
        level: LogLevel,
        message: str,
        logger: str = "",
        service: str = "",
        trace_id: str = "",
        span_id: str = "",
        **context: Any,
    ) -> LogEntry:
        """Create a log entry."""
        entry = LogEntry(
            level=level,
            message=message,
            logger=logger,
            service=service,
            trace_id=trace_id,
            span_id=span_id,
            context=context,
        )

        self._log_entries.append(entry)

        # Trim logs
        if len(self._log_entries) > self._settings.max_log_entries:
            self._log_entries = self._log_entries[-self._settings.max_log_entries:]

        # Notify handlers
        for handler in self._log_handlers:
            try:
                handler(entry)
            except Exception:
                pass

        return entry

    def debug(self, message: str, **kwargs: Any) -> LogEntry:
        """Log a debug message."""
        return self.log(LogLevel.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> LogEntry:
        """Log an info message."""
        return self.log(LogLevel.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> LogEntry:
        """Log a warning message."""
        return self.log(LogLevel.WARNING, message, **kwargs)

    def error(self, message: str, exception: str | None = None, **kwargs: Any) -> LogEntry:
        """Log an error message."""
        return self.log(LogLevel.ERROR, message, exception=exception, **kwargs)

    def critical(self, message: str, exception: str | None = None, **kwargs: Any) -> LogEntry:
        """Log a critical message."""
        return self.log(LogLevel.CRITICAL, message, exception=exception, **kwargs)

    def get_logs(
        self,
        level: LogLevel | None = None,
        service: str | None = None,
        logger: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[LogEntry]:
        """Get log entries with filters."""
        logs = self._log_entries.copy()

        if level:
            logs = [l for l in logs if l.level == level]

        if service:
            logs = [l for l in logs if l.service == service]

        if logger:
            logs = [l for l in logs if l.logger == logger]

        if start_time:
            logs = [l for l in logs if l.timestamp >= start_time]

        if end_time:
            logs = [l for l in logs if l.timestamp <= end_time]

        logs.sort(key=lambda l: l.timestamp, reverse=True)
        return logs[:limit]

    def register_log_handler(self, handler: Callable[[LogEntry], None]) -> None:
        """Register a log handler."""
        self._log_handlers.append(handler)

    # ===========================================
    # TRACING
    # ===========================================

    def start_trace(
        self,
        name: str,
        service: str = "",
        operation: str = "",
        tags: dict[str, str] | None = None,
    ) -> Trace:
        """Start a new trace."""
        trace = Trace(
            service=service,
            operation=operation or name,
            tags=tags or {},
        )

        self._traces[trace.trace_id] = trace
        return trace

    def start_span(
        self,
        trace_id: str,
        name: str,
        parent_span_id: str = "",
        service: str = "",
        operation: str = "",
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        """Start a new span in a trace."""
        span = Span(
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            name=name,
            service=service,
            operation=operation or name,
            attributes=attributes or {},
        )

        trace = self._traces.get(trace_id)
        if trace:
            if not trace.root_span_id:
                trace.root_span_id = span.span_id
            trace.spans.append(span)

        self._active_spans[span.span_id] = span
        return span

    def end_span(
        self,
        span_id: str,
        status: str = "ok",
        status_message: str = "",
    ) -> Span | None:
        """End a span."""
        span = self._active_spans.pop(span_id, None)
        if not span:
            return None

        span.end_time = datetime.utcnow()
        span.duration_ms = (span.end_time - span.start_time).total_seconds() * 1000
        span.status = status
        span.status_message = status_message

        return span

    def end_trace(self, trace_id: str) -> Trace | None:
        """End a trace."""
        trace = self._traces.get(trace_id)
        if not trace:
            return None

        trace.end_time = datetime.utcnow()
        trace.duration_ms = (trace.end_time - trace.start_time).total_seconds() * 1000

        # Determine overall status
        if any(s.status == "error" for s in trace.spans):
            trace.status = "error"
        else:
            trace.status = "ok"

        return trace

    def get_trace(self, trace_id: str) -> Trace | None:
        """Get a trace by ID."""
        return self._traces.get(trace_id)

    def get_recent_traces(
        self,
        limit: int = 50,
        service: str | None = None,
    ) -> list[Trace]:
        """Get recent traces."""
        traces = list(self._traces.values())

        if service:
            traces = [t for t in traces if t.service == service]

        traces.sort(key=lambda t: t.start_time, reverse=True)
        return traces[:limit]

    # ===========================================
    # SYSTEM STATUS
    # ===========================================

    async def get_system_status(self) -> SystemStatus:
        """Get overall system status."""
        services = self._health.get_all_services()
        active_alerts = len(self._alerts.get_active_alerts())

        # Calculate metrics
        total_requests = self._metrics.get_metric_value("requests_total") or 0
        total_errors = self._metrics.get_metric_value("errors_total") or 0
        error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0.0

        # Get average response time from timer
        timer = self._metrics.timer("request_duration_seconds")
        avg_response_time = timer.get_mean() * 1000 if timer else 0.0

        return SystemStatus(
            status=self._health.get_overall_status(),
            services=services,
            active_alerts=active_alerts,
            total_requests=int(total_requests),
            error_rate=error_rate,
            avg_response_time_ms=avg_response_time,
            uptime_seconds=(datetime.utcnow() - self._start_time).total_seconds(),
        )

    # ===========================================
    # STATISTICS
    # ===========================================

    async def get_stats(self) -> MonitoringStats:
        """Get monitoring statistics."""
        metric_stats = self._metrics.get_stats()
        health_summary = self._health.get_summary()
        alert_stats = self._alerts.get_stats()

        return MonitoringStats(
            total_metrics=metric_stats["total_metrics"],
            total_counters=metric_stats["total_counters"],
            total_gauges=metric_stats["total_gauges"],
            total_histograms=metric_stats["total_histograms"],
            total_timers=metric_stats["total_timers"],
            total_health_checks=health_summary["total_checks"],
            healthy_services=health_summary["healthy_services"],
            unhealthy_services=health_summary["unhealthy_services"],
            total_alert_rules=alert_stats["total_rules"],
            active_alerts=alert_stats["active_alerts"],
            total_log_entries=len(self._log_entries),
            total_traces=len(self._traces),
            uptime_seconds=(datetime.utcnow() - self._start_time).total_seconds(),
        )


# Singleton instance
_service: MonitoringService | None = None


def get_monitoring_service() -> MonitoringService:
    """Get or create monitoring service singleton."""
    global _service
    if _service is None:
        _service = MonitoringService()
    return _service


__all__ = [
    "MonitoringStats",
    "MonitoringService",
    "get_monitoring_service",
]

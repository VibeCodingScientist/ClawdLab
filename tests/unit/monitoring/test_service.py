"""Unit tests for MonitoringService."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from platform.monitoring.service import MonitoringService, MonitoringStats
from platform.monitoring.base import (
    Alert,
    AlertRule,
    AlertSeverity,
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


class TestMonitoringService:
    """Tests for MonitoringService class."""

    @pytest.fixture
    def mock_metrics(self) -> MagicMock:
        """Create mock metrics collector."""
        mock = MagicMock()
        mock.create_counter.return_value = MagicMock()
        mock.create_gauge.return_value = MagicMock()
        mock.create_histogram.return_value = MagicMock()
        mock.create_timer.return_value = MagicMock()
        mock.increment.return_value = None
        mock.set_gauge.return_value = None
        mock.observe.return_value = None
        mock.record_time.return_value = None
        mock.get_metric.return_value = MagicMock(name="test_metric")
        mock.get_metric_value.return_value = 100.0
        mock.get_all_metrics.return_value = [MagicMock(), MagicMock()]
        mock.collect.return_value = {"metric1": 100, "metric2": 200}
        mock.export_prometheus.return_value = "# HELP metric\nmetric 100"
        mock.timer.return_value = MagicMock(get_mean=MagicMock(return_value=0.5))
        mock.get_stats.return_value = {
            "total_metrics": 10,
            "total_counters": 3,
            "total_gauges": 3,
            "total_histograms": 2,
            "total_timers": 2,
        }
        return mock

    @pytest.fixture
    def mock_health(self) -> AsyncMock:
        """Create mock health service."""
        mock = AsyncMock()
        mock.start.return_value = None
        mock.stop.return_value = None
        mock.register_check.return_value = MagicMock()
        mock.register_http_check.return_value = MagicMock()
        mock.register_tcp_check.return_value = MagicMock()
        mock.run_all_checks.return_value = {"check1": HealthCheckResult(status=HealthStatus.HEALTHY)}
        mock.liveness.return_value = HealthCheckResult(status=HealthStatus.HEALTHY)
        mock.readiness.return_value = HealthCheckResult(status=HealthStatus.HEALTHY)
        mock.get_service.return_value = ServiceHealth(name="test-service", status=HealthStatus.HEALTHY)
        mock.get_all_services.return_value = [
            ServiceHealth(name="service1", status=HealthStatus.HEALTHY),
            ServiceHealth(name="service2", status=HealthStatus.HEALTHY),
        ]
        mock.get_overall_status.return_value = HealthStatus.HEALTHY
        mock.get_summary.return_value = {
            "total_checks": 5,
            "healthy_services": 4,
            "unhealthy_services": 1,
        }
        return mock

    @pytest.fixture
    def mock_alerts(self) -> AsyncMock:
        """Create mock alert manager."""
        mock = AsyncMock()
        mock.start.return_value = None
        mock.stop.return_value = None
        mock.create_rule.return_value = AlertRule(
            name="test-rule",
            metric_name="test_metric",
            operator=">",
            threshold=100.0,
        )
        mock.get_rule.return_value = AlertRule(name="test-rule")
        mock.get_all_rules.return_value = [AlertRule(name="rule1"), AlertRule(name="rule2")]
        mock.delete_rule.return_value = True
        mock.get_active_alerts.return_value = [Alert(rule_id="rule1", severity=AlertSeverity.WARNING)]
        mock.get_alert.return_value = Alert(rule_id="rule1")
        mock.get_alert_history.return_value = [Alert(rule_id="rule1"), Alert(rule_id="rule2")]
        mock.acknowledge_alert.return_value = Alert(rule_id="rule1", acknowledged=True)
        mock.resolve_alert.return_value = Alert(rule_id="rule1", resolved=True)
        mock.create_silence.return_value = "silence-id-123"
        mock.get_stats.return_value = {
            "total_rules": 10,
            "active_alerts": 3,
        }
        return mock

    @pytest.fixture
    def service(self, mock_metrics, mock_health, mock_alerts) -> MonitoringService:
        """Create service with mocked dependencies."""
        return MonitoringService(
            metrics_collector=mock_metrics,
            health_service=mock_health,
            alert_manager=mock_alerts,
        )

    # ===================================
    # LIFECYCLE TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_start(self, service: MonitoringService, mock_health, mock_alerts):
        """Test starting monitoring service."""
        await service.start()

        mock_health.start.assert_called_once()
        mock_alerts.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop(self, service: MonitoringService, mock_health, mock_alerts):
        """Test stopping monitoring service."""
        await service.stop()

        mock_health.stop.assert_called_once()
        mock_alerts.stop.assert_called_once()

    # ===================================
    # METRICS TESTS
    # ===================================

    def test_create_counter(self, service: MonitoringService, mock_metrics):
        """Test creating a counter metric."""
        counter = service.create_counter(
            name="requests_total",
            description="Total requests",
            labels=["method", "path"],
        )

        mock_metrics.create_counter.assert_called_once_with(
            "requests_total", "Total requests", ["method", "path"]
        )

    def test_create_gauge(self, service: MonitoringService, mock_metrics):
        """Test creating a gauge metric."""
        gauge = service.create_gauge(
            name="active_connections",
            description="Active connections",
        )

        mock_metrics.create_gauge.assert_called_once()

    def test_create_histogram(self, service: MonitoringService, mock_metrics):
        """Test creating a histogram metric."""
        histogram = service.create_histogram(
            name="request_duration",
            description="Request duration",
            buckets=[0.1, 0.5, 1.0],
        )

        mock_metrics.create_histogram.assert_called_once()

    def test_create_timer(self, service: MonitoringService, mock_metrics):
        """Test creating a timer metric."""
        timer = service.create_timer(
            name="processing_time",
            description="Processing time",
        )

        mock_metrics.create_timer.assert_called_once()

    def test_increment(self, service: MonitoringService, mock_metrics):
        """Test incrementing a counter."""
        service.increment("requests_total", 1.0, method="GET", path="/api")

        mock_metrics.increment.assert_called_once_with(
            "requests_total", 1.0, method="GET", path="/api"
        )

    def test_set_gauge(self, service: MonitoringService, mock_metrics):
        """Test setting a gauge value."""
        service.set_gauge("active_connections", 50.0, host="server1")

        mock_metrics.set_gauge.assert_called_once_with(
            "active_connections", 50.0, host="server1"
        )

    def test_observe(self, service: MonitoringService, mock_metrics):
        """Test observing a histogram value."""
        service.observe("request_duration", 0.25, endpoint="/api/v1")

        mock_metrics.observe.assert_called_once_with(
            "request_duration", 0.25, endpoint="/api/v1"
        )

    def test_record_time(self, service: MonitoringService, mock_metrics):
        """Test recording time for a timer."""
        service.record_time("processing_time", 150.0, task="analysis")

        mock_metrics.record_time.assert_called_once_with(
            "processing_time", 150.0, task="analysis"
        )

    def test_get_metric(self, service: MonitoringService, mock_metrics):
        """Test getting a metric by name."""
        metric = service.get_metric("test_metric")

        assert metric is not None
        mock_metrics.get_metric.assert_called_once_with("test_metric")

    def test_get_metric_value(self, service: MonitoringService, mock_metrics):
        """Test getting metric value."""
        value = service.get_metric_value("test_metric", label="value")

        assert value == 100.0

    def test_get_all_metrics(self, service: MonitoringService, mock_metrics):
        """Test getting all metrics."""
        metrics = service.get_all_metrics()

        assert len(metrics) == 2

    def test_collect_metrics(self, service: MonitoringService, mock_metrics):
        """Test collecting all metric values."""
        collected = service.collect_metrics()

        assert "metric1" in collected
        mock_metrics.collect.assert_called_once()

    def test_export_prometheus(self, service: MonitoringService, mock_metrics):
        """Test exporting metrics in Prometheus format."""
        output = service.export_prometheus()

        assert "# HELP" in output
        mock_metrics.export_prometheus.assert_called_once()

    # ===================================
    # HEALTH CHECK TESTS
    # ===================================

    def test_register_health_check(self, service: MonitoringService, mock_health):
        """Test registering a health check."""
        check_fn = MagicMock(return_value=HealthCheckResult(status=HealthStatus.HEALTHY))

        check = service.register_health_check(
            name="database",
            check_fn=check_fn,
            service="db-service",
            check_type="database",
        )

        mock_health.register_check.assert_called_once()

    def test_register_http_check(self, service: MonitoringService, mock_health):
        """Test registering an HTTP health check."""
        check = service.register_http_check(
            name="api",
            url="http://localhost:8000/health",
            service="api-service",
        )

        mock_health.register_http_check.assert_called_once_with(
            "api", "http://localhost:8000/health", "api-service"
        )

    def test_register_tcp_check(self, service: MonitoringService, mock_health):
        """Test registering a TCP health check."""
        check = service.register_tcp_check(
            name="redis",
            host="localhost",
            port=6379,
            service="cache-service",
        )

        mock_health.register_tcp_check.assert_called_once_with(
            "redis", "localhost", 6379, "cache-service"
        )

    @pytest.mark.asyncio
    async def test_run_health_checks(self, service: MonitoringService, mock_health):
        """Test running all health checks."""
        results = await service.run_health_checks()

        assert "check1" in results
        mock_health.run_all_checks.assert_called_once()

    @pytest.mark.asyncio
    async def test_liveness(self, service: MonitoringService, mock_health):
        """Test liveness check."""
        result = await service.liveness()

        assert result.status == HealthStatus.HEALTHY
        mock_health.liveness.assert_called_once()

    @pytest.mark.asyncio
    async def test_readiness(self, service: MonitoringService, mock_health):
        """Test readiness check."""
        result = await service.readiness()

        assert result.status == HealthStatus.HEALTHY
        mock_health.readiness.assert_called_once()

    def test_get_service_health(self, service: MonitoringService, mock_health):
        """Test getting service health."""
        health = service.get_service_health("test-service")

        assert health is not None
        assert health.status == HealthStatus.HEALTHY

    def test_get_all_services(self, service: MonitoringService, mock_health):
        """Test getting all services health."""
        services = service.get_all_services()

        assert len(services) == 2

    def test_get_overall_health(self, service: MonitoringService, mock_health):
        """Test getting overall health status."""
        status = service.get_overall_health()

        assert status == HealthStatus.HEALTHY

    def test_get_health_summary(self, service: MonitoringService, mock_health):
        """Test getting health summary."""
        summary = service.get_health_summary()

        assert "total_checks" in summary
        assert summary["healthy_services"] == 4

    # ===================================
    # ALERTING TESTS
    # ===================================

    def test_create_alert_rule(self, service: MonitoringService, mock_alerts):
        """Test creating an alert rule."""
        rule = service.create_alert_rule(
            name="high-cpu",
            metric_name="cpu_usage",
            operator=">",
            threshold=80.0,
            severity=AlertSeverity.WARNING,
            duration_seconds=300,
            description="CPU usage is high",
        )

        assert rule is not None
        mock_alerts.create_rule.assert_called_once()

    def test_get_alert_rule(self, service: MonitoringService, mock_alerts):
        """Test getting an alert rule."""
        rule = service.get_alert_rule("rule-123")

        assert rule is not None
        mock_alerts.get_rule.assert_called_once_with("rule-123")

    def test_get_all_rules(self, service: MonitoringService, mock_alerts):
        """Test getting all alert rules."""
        rules = service.get_all_rules()

        assert len(rules) == 2

    def test_delete_alert_rule(self, service: MonitoringService, mock_alerts):
        """Test deleting an alert rule."""
        result = service.delete_alert_rule("rule-123")

        assert result is True
        mock_alerts.delete_rule.assert_called_once_with("rule-123")

    def test_get_active_alerts(self, service: MonitoringService, mock_alerts):
        """Test getting active alerts."""
        alerts = service.get_active_alerts()

        assert len(alerts) == 1

    def test_get_alert(self, service: MonitoringService, mock_alerts):
        """Test getting an alert by ID."""
        alert = service.get_alert("alert-123")

        assert alert is not None
        mock_alerts.get_alert.assert_called_once_with("alert-123")

    def test_get_alert_history(self, service: MonitoringService, mock_alerts):
        """Test getting alert history."""
        history = service.get_alert_history(limit=50, severity=AlertSeverity.WARNING)

        assert len(history) == 2
        mock_alerts.get_alert_history.assert_called_once()

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, service: MonitoringService, mock_alerts):
        """Test acknowledging an alert."""
        alert = await service.acknowledge_alert("alert-123", "user-1")

        assert alert is not None
        mock_alerts.acknowledge_alert.assert_called_once_with("alert-123", "user-1")

    @pytest.mark.asyncio
    async def test_resolve_alert(self, service: MonitoringService, mock_alerts):
        """Test resolving an alert."""
        alert = await service.resolve_alert("alert-123")

        assert alert is not None
        mock_alerts.resolve_alert.assert_called_once_with("alert-123")

    def test_create_silence(self, service: MonitoringService, mock_alerts):
        """Test creating a silence."""
        silence_id = service.create_silence(
            matchers={"service": "api"},
            duration_seconds=3600,
            created_by="user-1",
            comment="Maintenance window",
        )

        assert silence_id == "silence-id-123"
        mock_alerts.create_silence.assert_called_once()

    def test_get_alert_stats(self, service: MonitoringService, mock_alerts):
        """Test getting alert statistics."""
        stats = service.get_alert_stats()

        assert stats["total_rules"] == 10
        assert stats["active_alerts"] == 3

    # ===================================
    # LOGGING TESTS
    # ===================================

    def test_log_entry(self, service: MonitoringService):
        """Test creating a log entry."""
        entry = service.log(
            level=LogLevel.INFO,
            message="Test message",
            logger="test.logger",
            service="test-service",
            user_id="user-1",
        )

        assert entry is not None
        assert entry.level == LogLevel.INFO
        assert entry.message == "Test message"
        assert entry.context["user_id"] == "user-1"

    def test_log_debug(self, service: MonitoringService):
        """Test debug logging."""
        entry = service.debug("Debug message", key="value")

        assert entry.level == LogLevel.DEBUG

    def test_log_info(self, service: MonitoringService):
        """Test info logging."""
        entry = service.info("Info message")

        assert entry.level == LogLevel.INFO

    def test_log_warning(self, service: MonitoringService):
        """Test warning logging."""
        entry = service.warning("Warning message")

        assert entry.level == LogLevel.WARNING

    def test_log_error(self, service: MonitoringService):
        """Test error logging."""
        entry = service.error("Error message", exception="ValueError")

        assert entry.level == LogLevel.ERROR

    def test_log_critical(self, service: MonitoringService):
        """Test critical logging."""
        entry = service.critical("Critical message", exception="SystemError")

        assert entry.level == LogLevel.CRITICAL

    def test_get_logs(self, service: MonitoringService):
        """Test getting logs with filters."""
        service.info("Info 1", service="service-a")
        service.warning("Warning 1", service="service-b")
        service.info("Info 2", service="service-a")

        all_logs = service.get_logs()
        assert len(all_logs) == 3

        info_logs = service.get_logs(level=LogLevel.INFO)
        assert len(info_logs) == 2

        service_a_logs = service.get_logs(service="service-a")
        assert len(service_a_logs) == 2

    def test_get_logs_pagination(self, service: MonitoringService):
        """Test getting logs with pagination."""
        for i in range(10):
            service.info(f"Message {i}")

        logs = service.get_logs(limit=5)
        assert len(logs) == 5

    def test_log_trimming(self, service: MonitoringService):
        """Test that logs are trimmed at max limit."""
        # Override max for testing
        service._settings = MagicMock()
        service._settings.max_log_entries = 5

        for i in range(10):
            service.info(f"Message {i}")

        assert len(service._log_entries) == 5

    def test_log_handler(self, service: MonitoringService):
        """Test log handler notification."""
        handler = MagicMock()
        service.register_log_handler(handler)

        service.info("Test message")

        handler.assert_called_once()
        call_args = handler.call_args[0]
        assert call_args[0].message == "Test message"

    # ===================================
    # TRACING TESTS
    # ===================================

    def test_start_trace(self, service: MonitoringService):
        """Test starting a trace."""
        trace = service.start_trace(
            name="process-request",
            service="api",
            operation="handle_request",
            tags={"endpoint": "/api/v1"},
        )

        assert trace is not None
        assert trace.service == "api"
        assert trace.trace_id in service._traces

    def test_start_span(self, service: MonitoringService):
        """Test starting a span."""
        trace = service.start_trace("test-trace", service="api")

        span = service.start_span(
            trace_id=trace.trace_id,
            name="database-query",
            service="db",
            operation="SELECT",
            attributes={"table": "users"},
        )

        assert span is not None
        assert span.trace_id == trace.trace_id
        assert span.span_id in service._active_spans
        assert len(trace.spans) == 1

    def test_start_span_sets_root(self, service: MonitoringService):
        """Test that first span becomes root span."""
        trace = service.start_trace("test-trace")

        span = service.start_span(trace.trace_id, "first-span")

        assert trace.root_span_id == span.span_id

    def test_start_span_with_parent(self, service: MonitoringService):
        """Test starting a child span."""
        trace = service.start_trace("test-trace")
        parent = service.start_span(trace.trace_id, "parent-span")
        child = service.start_span(
            trace.trace_id,
            "child-span",
            parent_span_id=parent.span_id,
        )

        assert child.parent_span_id == parent.span_id

    def test_end_span(self, service: MonitoringService):
        """Test ending a span."""
        trace = service.start_trace("test-trace")
        span = service.start_span(trace.trace_id, "test-span")

        ended = service.end_span(span.span_id, status="ok", status_message="Success")

        assert ended is not None
        assert ended.end_time is not None
        assert ended.duration_ms is not None
        assert ended.status == "ok"
        assert span.span_id not in service._active_spans

    def test_end_span_not_found(self, service: MonitoringService):
        """Test ending non-existent span."""
        result = service.end_span("non-existent")
        assert result is None

    def test_end_trace(self, service: MonitoringService):
        """Test ending a trace."""
        trace = service.start_trace("test-trace")
        span = service.start_span(trace.trace_id, "test-span")
        service.end_span(span.span_id, status="ok")

        ended = service.end_trace(trace.trace_id)

        assert ended is not None
        assert ended.end_time is not None
        assert ended.duration_ms is not None
        assert ended.status == "ok"

    def test_end_trace_with_error(self, service: MonitoringService):
        """Test ending trace with error span sets error status."""
        trace = service.start_trace("test-trace")
        span = service.start_span(trace.trace_id, "test-span")
        service.end_span(span.span_id, status="error")

        ended = service.end_trace(trace.trace_id)

        assert ended.status == "error"

    def test_get_trace(self, service: MonitoringService):
        """Test getting a trace by ID."""
        trace = service.start_trace("test-trace")

        retrieved = service.get_trace(trace.trace_id)

        assert retrieved is not None
        assert retrieved.trace_id == trace.trace_id

    def test_get_recent_traces(self, service: MonitoringService):
        """Test getting recent traces."""
        service.start_trace("trace-1", service="api")
        service.start_trace("trace-2", service="api")
        service.start_trace("trace-3", service="db")

        all_traces = service.get_recent_traces()
        assert len(all_traces) == 3

        api_traces = service.get_recent_traces(service="api")
        assert len(api_traces) == 2

    # ===================================
    # SYSTEM STATUS TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_get_system_status(
        self, service: MonitoringService, mock_health, mock_alerts, mock_metrics
    ):
        """Test getting system status."""
        status = await service.get_system_status()

        assert status is not None
        assert status.status == HealthStatus.HEALTHY
        assert len(status.services) == 2
        assert status.uptime_seconds > 0

    # ===================================
    # STATISTICS TESTS
    # ===================================

    @pytest.mark.asyncio
    async def test_get_stats(
        self, service: MonitoringService, mock_metrics, mock_health, mock_alerts
    ):
        """Test getting monitoring statistics."""
        # Add some data
        service.info("Test log")
        service.start_trace("test-trace")

        stats = await service.get_stats()

        assert isinstance(stats, MonitoringStats)
        assert stats.total_metrics == 10
        assert stats.total_health_checks == 5
        assert stats.total_alert_rules == 10
        assert stats.active_alerts == 3
        assert stats.total_log_entries >= 1
        assert stats.total_traces >= 1
        assert stats.uptime_seconds > 0

"""REST API endpoints for Monitoring and Observability."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from platform.monitoring.base import AlertSeverity, LogLevel
from platform.monitoring.service import get_monitoring_service


router = APIRouter(prefix="/monitoring", tags=["monitoring"])


# ===========================================
# REQUEST/RESPONSE MODELS
# ===========================================


class AlertRuleCreateRequest(BaseModel):
    """Request to create an alert rule."""

    name: str = Field(..., description="Rule name")
    metric_name: str = Field(..., description="Metric to monitor")
    operator: str = Field(..., description="Comparison operator (>, <, >=, <=, ==, !=)")
    threshold: float = Field(..., description="Threshold value")
    severity: str = Field(default="warning", description="Alert severity")
    duration_seconds: int = Field(default=0, ge=0, description="Duration before firing")
    description: str = Field(default="", description="Rule description")


class AlertAcknowledgeRequest(BaseModel):
    """Request to acknowledge an alert."""

    acknowledged_by: str = Field(..., description="Who acknowledged the alert")


class SilenceCreateRequest(BaseModel):
    """Request to create a silence."""

    matchers: dict[str, str] = Field(..., description="Label matchers")
    duration_seconds: int = Field(..., gt=0, description="Silence duration")
    created_by: str = Field(..., description="Who created the silence")
    comment: str = Field(default="", description="Silence comment")


class LogRequest(BaseModel):
    """Request to create a log entry."""

    level: str = Field(default="INFO", description="Log level")
    message: str = Field(..., description="Log message")
    logger: str = Field(default="", description="Logger name")
    service: str = Field(default="", description="Service name")
    context: dict[str, Any] = Field(default={}, description="Additional context")


class MetricRecordRequest(BaseModel):
    """Request to record a metric value."""

    name: str = Field(..., description="Metric name")
    value: float = Field(..., description="Metric value")
    labels: dict[str, str] = Field(default={}, description="Metric labels")


class HealthCheckRegisterRequest(BaseModel):
    """Request to register a health check."""

    name: str = Field(..., description="Check name")
    check_type: str = Field(default="http", description="Check type (http, tcp)")
    target: str = Field(..., description="Target URL or host:port")
    service: str = Field(default="", description="Associated service")


# ===========================================
# METRICS ENDPOINTS
# ===========================================


@router.get("/metrics")
async def get_metrics():
    """Get all current metric values."""
    service = get_monitoring_service()
    return service.collect_metrics()


@router.get("/metrics/prometheus", response_class=PlainTextResponse)
async def get_metrics_prometheus():
    """Get metrics in Prometheus format."""
    service = get_monitoring_service()
    return service.export_prometheus()


@router.get("/metrics/{metric_name}")
async def get_metric(
    metric_name: str,
    labels: str | None = Query(default=None, description="Label filter (key=value,key=value)"),
):
    """Get a specific metric."""
    service = get_monitoring_service()
    metric = service.get_metric(metric_name)

    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")

    # Parse labels
    label_dict = {}
    if labels:
        for pair in labels.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                label_dict[k] = v

    value = service.get_metric_value(metric_name, **label_dict)

    return {
        "metric": metric.to_dict(),
        "current_value": value,
    }


@router.get("/metrics/list")
async def list_metrics():
    """List all registered metrics."""
    service = get_monitoring_service()
    metrics = service.get_all_metrics()
    return {"metrics": [m.to_dict() for m in metrics], "total": len(metrics)}


@router.post("/metrics/record")
async def record_metric(request: MetricRecordRequest):
    """Record a metric value."""
    service = get_monitoring_service()

    # Determine metric type and record
    metric = service.get_metric(request.name)
    if not metric:
        # Create gauge if doesn't exist
        service.set_gauge(request.name, request.value, **request.labels)
    else:
        if metric.metric_type.value == "counter":
            service.increment(request.name, request.value, **request.labels)
        elif metric.metric_type.value == "gauge":
            service.set_gauge(request.name, request.value, **request.labels)
        elif metric.metric_type.value == "histogram":
            service.observe(request.name, request.value, **request.labels)
        elif metric.metric_type.value == "timer":
            service.record_time(request.name, request.value, **request.labels)

    return {"status": "recorded", "metric": request.name, "value": request.value}


# ===========================================
# HEALTH CHECK ENDPOINTS
# ===========================================


@router.get("/health")
async def get_health():
    """Get overall health status."""
    service = get_monitoring_service()
    return service.get_health_summary()


@router.get("/health/live")
async def liveness():
    """Kubernetes liveness probe."""
    service = get_monitoring_service()
    result = await service.liveness()
    return result.to_dict()


@router.get("/health/ready")
async def readiness():
    """Kubernetes readiness probe."""
    service = get_monitoring_service()
    result = await service.readiness()

    if result.status.value != "healthy":
        raise HTTPException(status_code=503, detail=result.message)

    return result.to_dict()


@router.get("/health/services")
async def get_all_services():
    """Get health status for all services."""
    service = get_monitoring_service()
    services = service.get_all_services()
    return {"services": [s.to_dict() for s in services], "total": len(services)}


@router.get("/health/services/{service_name}")
async def get_service_health(service_name: str):
    """Get health status for a specific service."""
    service = get_monitoring_service()
    health = service.get_service_health(service_name)

    if not health:
        raise HTTPException(status_code=404, detail="Service not found")

    return health.to_dict()


@router.post("/health/checks")
async def register_health_check(request: HealthCheckRegisterRequest):
    """Register a health check."""
    service = get_monitoring_service()

    if request.check_type == "http":
        check = service.register_http_check(
            name=request.name,
            url=request.target,
            service=request.service,
        )
    elif request.check_type == "tcp":
        # Parse host:port
        if ":" not in request.target:
            raise HTTPException(status_code=400, detail="TCP target must be host:port")
        host, port = request.target.rsplit(":", 1)
        check = service.register_tcp_check(
            name=request.name,
            host=host,
            port=int(port),
            service=request.service,
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported check type")

    return check.to_dict()


@router.post("/health/run")
async def run_health_checks():
    """Run all health checks."""
    service = get_monitoring_service()
    results = await service.run_health_checks()
    return {"results": {k: v.to_dict() for k, v in results.items()}}


# ===========================================
# ALERT ENDPOINTS
# ===========================================


@router.post("/alerts/rules")
async def create_alert_rule(request: AlertRuleCreateRequest):
    """Create an alert rule."""
    service = get_monitoring_service()

    try:
        severity = AlertSeverity(request.severity)
    except ValueError:
        severity = AlertSeverity.WARNING

    rule = service.create_alert_rule(
        name=request.name,
        metric_name=request.metric_name,
        operator=request.operator,
        threshold=request.threshold,
        severity=severity,
        duration_seconds=request.duration_seconds,
        description=request.description,
    )

    return rule.to_dict()


@router.get("/alerts/rules")
async def list_alert_rules():
    """List all alert rules."""
    service = get_monitoring_service()
    rules = service.get_all_rules()
    return {"rules": [r.to_dict() for r in rules], "total": len(rules)}


@router.get("/alerts/rules/{rule_id}")
async def get_alert_rule(rule_id: str):
    """Get an alert rule by ID."""
    service = get_monitoring_service()
    rule = service.get_alert_rule(rule_id)

    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    return rule.to_dict()


@router.delete("/alerts/rules/{rule_id}")
async def delete_alert_rule(rule_id: str):
    """Delete an alert rule."""
    service = get_monitoring_service()

    if service.delete_alert_rule(rule_id):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Rule not found")


@router.get("/alerts/active")
async def get_active_alerts():
    """Get all active alerts."""
    service = get_monitoring_service()
    alerts = service.get_active_alerts()
    return {"alerts": [a.to_dict() for a in alerts], "total": len(alerts)}


@router.get("/alerts/{alert_id}")
async def get_alert(alert_id: str):
    """Get an alert by ID."""
    service = get_monitoring_service()
    alert = service.get_alert(alert_id)

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return alert.to_dict()


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, request: AlertAcknowledgeRequest):
    """Acknowledge an alert."""
    service = get_monitoring_service()
    alert = await service.acknowledge_alert(alert_id, request.acknowledged_by)

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return alert.to_dict()


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """Resolve an alert."""
    service = get_monitoring_service()
    alert = await service.resolve_alert(alert_id)

    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    return alert.to_dict()


@router.get("/alerts/history")
async def get_alert_history(
    limit: int = Query(default=100, ge=1, le=1000, description="Limit"),
    severity: str | None = Query(default=None, description="Filter by severity"),
):
    """Get alert history."""
    service = get_monitoring_service()

    sev = AlertSeverity(severity) if severity else None
    history = service.get_alert_history(limit=limit, severity=sev)

    return {"alerts": [a.to_dict() for a in history], "total": len(history)}


@router.post("/alerts/silences")
async def create_silence(request: SilenceCreateRequest):
    """Create a silence."""
    service = get_monitoring_service()

    silence_id = service.create_silence(
        matchers=request.matchers,
        duration_seconds=request.duration_seconds,
        created_by=request.created_by,
        comment=request.comment,
    )

    return {"silence_id": silence_id, "status": "created"}


@router.get("/alerts/stats")
async def get_alert_stats():
    """Get alerting statistics."""
    service = get_monitoring_service()
    return service.get_alert_stats()


# ===========================================
# LOGGING ENDPOINTS
# ===========================================


@router.post("/logs")
async def create_log(request: LogRequest):
    """Create a log entry."""
    service = get_monitoring_service()

    try:
        level = LogLevel(request.level.upper())
    except ValueError:
        level = LogLevel.INFO

    entry = service.log(
        level=level,
        message=request.message,
        logger=request.logger,
        service=request.service,
        **request.context,
    )

    return entry.to_dict()


@router.get("/logs")
async def get_logs(
    level: str | None = Query(default=None, description="Filter by level"),
    service_name: str | None = Query(default=None, description="Filter by service"),
    logger: str | None = Query(default=None, description="Filter by logger"),
    limit: int = Query(default=100, ge=1, le=1000, description="Limit"),
):
    """Get log entries."""
    service = get_monitoring_service()

    log_level = LogLevel(level.upper()) if level else None

    logs = service.get_logs(
        level=log_level,
        service=service_name,
        logger=logger,
        limit=limit,
    )

    return {"logs": [l.to_dict() for l in logs], "total": len(logs)}


# ===========================================
# TRACING ENDPOINTS
# ===========================================


@router.get("/traces")
async def get_traces(
    limit: int = Query(default=50, ge=1, le=500, description="Limit"),
    service_name: str | None = Query(default=None, description="Filter by service"),
):
    """Get recent traces."""
    service = get_monitoring_service()
    traces = service.get_recent_traces(limit=limit, service=service_name)
    return {"traces": [t.to_dict() for t in traces], "total": len(traces)}


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str):
    """Get a trace by ID."""
    service = get_monitoring_service()
    trace = service.get_trace(trace_id)

    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")

    return trace.to_dict()


# ===========================================
# STATUS ENDPOINTS
# ===========================================


@router.get("/status")
async def get_system_status():
    """Get overall system status."""
    service = get_monitoring_service()
    status = await service.get_system_status()
    return status.to_dict()


@router.get("/stats")
async def get_stats():
    """Get monitoring statistics."""
    service = get_monitoring_service()
    stats = await service.get_stats()

    return {
        "total_metrics": stats.total_metrics,
        "total_counters": stats.total_counters,
        "total_gauges": stats.total_gauges,
        "total_histograms": stats.total_histograms,
        "total_timers": stats.total_timers,
        "total_health_checks": stats.total_health_checks,
        "healthy_services": stats.healthy_services,
        "unhealthy_services": stats.unhealthy_services,
        "total_alert_rules": stats.total_alert_rules,
        "active_alerts": stats.active_alerts,
        "total_log_entries": stats.total_log_entries,
        "total_traces": stats.total_traces,
        "uptime_seconds": stats.uptime_seconds,
    }


__all__ = ["router"]

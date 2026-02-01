"""Alerting System."""

import asyncio
import operator
from datetime import datetime, timedelta
from typing import Any, Callable

from platform.monitoring.base import (
    Alert,
    AlertCondition,
    AlertRule,
    AlertSeverity,
    AlertState,
)
from platform.monitoring.config import get_settings
from platform.monitoring.metrics import MetricsCollector, get_metrics_collector


class AlertManager:
    """Manages alert rules and notifications."""

    def __init__(
        self,
        metrics_collector: MetricsCollector | None = None,
    ) -> None:
        self._settings = get_settings()
        self._metrics = metrics_collector or get_metrics_collector()

        self._rules: dict[str, AlertRule] = {}
        self._alerts: dict[str, Alert] = {}
        self._alert_history: list[Alert] = []
        self._silences: dict[str, dict[str, Any]] = {}
        self._notification_handlers: list[Callable[[Alert], None]] = []

        self._pending_conditions: dict[str, datetime] = {}  # rule_id -> first_true_time
        self._running = False
        self._task: asyncio.Task | None = None

        self._operators = {
            ">": operator.gt,
            "<": operator.lt,
            ">=": operator.ge,
            "<=": operator.le,
            "==": operator.eq,
            "!=": operator.ne,
        }

    async def start(self) -> None:
        """Start the alert evaluation loop."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_evaluation_loop())

    async def stop(self) -> None:
        """Stop the alert evaluation loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_evaluation_loop(self) -> None:
        """Run alert evaluation in a loop."""
        while self._running:
            try:
                await self.evaluate_all_rules()
                await asyncio.sleep(self._settings.alert_evaluation_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(5)

    # ===========================================
    # RULE MANAGEMENT
    # ===========================================

    def create_rule(
        self,
        name: str,
        metric_name: str,
        operator_str: str,
        threshold: float,
        severity: AlertSeverity = AlertSeverity.WARNING,
        duration_seconds: int = 0,
        description: str = "",
        labels: dict[str, str] | None = None,
        annotations: dict[str, str] | None = None,
    ) -> AlertRule:
        """Create an alert rule."""
        condition = AlertCondition(
            metric_name=metric_name,
            operator=operator_str,
            threshold=threshold,
            duration_seconds=duration_seconds,
            labels=labels or {},
        )

        rule = AlertRule(
            name=name,
            description=description,
            severity=severity,
            condition=condition,
            labels=labels or {},
            annotations=annotations or {},
        )

        self._rules[rule.rule_id] = rule
        return rule

    def update_rule(
        self,
        rule_id: str,
        **updates: Any,
    ) -> AlertRule | None:
        """Update an alert rule."""
        rule = self._rules.get(rule_id)
        if not rule:
            return None

        if "name" in updates:
            rule.name = updates["name"]
        if "description" in updates:
            rule.description = updates["description"]
        if "severity" in updates:
            rule.severity = AlertSeverity(updates["severity"])
        if "enabled" in updates:
            rule.enabled = updates["enabled"]
        if "threshold" in updates:
            rule.condition.threshold = updates["threshold"]
        if "operator" in updates:
            rule.condition.operator = updates["operator"]
        if "duration_seconds" in updates:
            rule.condition.duration_seconds = updates["duration_seconds"]
        if "labels" in updates:
            rule.labels = updates["labels"]
        if "annotations" in updates:
            rule.annotations = updates["annotations"]

        return rule

    def delete_rule(self, rule_id: str) -> bool:
        """Delete an alert rule."""
        if rule_id not in self._rules:
            return False

        del self._rules[rule_id]
        self._pending_conditions.pop(rule_id, None)

        # Resolve any active alerts for this rule
        for alert_id, alert in list(self._alerts.items()):
            if alert.rule_id == rule_id:
                alert.state = AlertState.RESOLVED
                alert.resolved_at = datetime.utcnow()
                self._alert_history.append(alert)
                del self._alerts[alert_id]

        return True

    def get_rule(self, rule_id: str) -> AlertRule | None:
        """Get an alert rule by ID."""
        return self._rules.get(rule_id)

    def get_all_rules(self) -> list[AlertRule]:
        """Get all alert rules."""
        return list(self._rules.values())

    def enable_rule(self, rule_id: str) -> bool:
        """Enable an alert rule."""
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = True
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """Disable an alert rule."""
        rule = self._rules.get(rule_id)
        if rule:
            rule.enabled = False
            self._pending_conditions.pop(rule_id, None)
            return True
        return False

    # ===========================================
    # ALERT EVALUATION
    # ===========================================

    async def evaluate_all_rules(self) -> list[Alert]:
        """Evaluate all enabled alert rules."""
        new_alerts = []

        for rule_id, rule in self._rules.items():
            if not rule.enabled:
                continue

            alert = await self.evaluate_rule(rule_id)
            if alert:
                new_alerts.append(alert)

        # Check for resolved alerts
        await self._check_resolved_alerts()

        return new_alerts

    async def evaluate_rule(self, rule_id: str) -> Alert | None:
        """Evaluate a single alert rule."""
        rule = self._rules.get(rule_id)
        if not rule or not rule.enabled:
            return None

        # Get current metric value
        condition = rule.condition
        value = self._metrics.get_metric_value(
            condition.metric_name,
            **condition.labels,
        )

        if value is None:
            return None

        # Check if condition is met
        op_fn = self._operators.get(condition.operator)
        if not op_fn:
            return None

        condition_met = op_fn(value, condition.threshold)

        if condition_met:
            # Handle duration requirement
            if condition.duration_seconds > 0:
                if rule_id not in self._pending_conditions:
                    self._pending_conditions[rule_id] = datetime.utcnow()
                    return None

                elapsed = (datetime.utcnow() - self._pending_conditions[rule_id]).total_seconds()
                if elapsed < condition.duration_seconds:
                    return None

            # Check if alert already exists
            existing_alert = self._find_active_alert(rule_id)
            if existing_alert:
                # Update existing alert value
                existing_alert.value = value
                return None

            # Check silences
            if self._is_silenced(rule):
                return None

            # Create new alert
            alert = await self._create_alert(rule, value)
            return alert

        else:
            # Condition not met - clear pending
            self._pending_conditions.pop(rule_id, None)

        return None

    def _find_active_alert(self, rule_id: str) -> Alert | None:
        """Find an active alert for a rule."""
        for alert in self._alerts.values():
            if alert.rule_id == rule_id and alert.state == AlertState.FIRING:
                return alert
        return None

    async def _create_alert(self, rule: AlertRule, value: float) -> Alert:
        """Create a new alert."""
        alert = Alert(
            rule_id=rule.rule_id,
            name=rule.name,
            severity=rule.severity,
            state=AlertState.FIRING,
            message=self._format_alert_message(rule, value),
            value=value,
            threshold=rule.condition.threshold,
            labels=rule.labels.copy(),
            annotations=rule.annotations.copy(),
        )

        self._alerts[alert.alert_id] = alert

        # Notify handlers
        await self._notify_handlers(alert)

        return alert

    def _format_alert_message(self, rule: AlertRule, value: float) -> str:
        """Format an alert message."""
        return (
            f"{rule.name}: {rule.condition.metric_name} "
            f"{rule.condition.operator} {rule.condition.threshold} "
            f"(current: {value:.2f})"
        )

    async def _check_resolved_alerts(self) -> None:
        """Check for alerts that should be resolved."""
        for alert_id, alert in list(self._alerts.items()):
            if alert.state != AlertState.FIRING:
                continue

            rule = self._rules.get(alert.rule_id)
            if not rule:
                # Rule deleted - resolve alert
                alert.state = AlertState.RESOLVED
                alert.resolved_at = datetime.utcnow()
                self._alert_history.append(alert)
                del self._alerts[alert_id]
                continue

            # Check if condition is still met
            condition = rule.condition
            value = self._metrics.get_metric_value(
                condition.metric_name,
                **condition.labels,
            )

            if value is None:
                continue

            op_fn = self._operators.get(condition.operator)
            if op_fn and not op_fn(value, condition.threshold):
                # Condition no longer met - resolve
                alert.state = AlertState.RESOLVED
                alert.resolved_at = datetime.utcnow()
                self._alert_history.append(alert)
                del self._alerts[alert_id]

                # Notify resolution
                await self._notify_handlers(alert)

    # ===========================================
    # ALERT MANAGEMENT
    # ===========================================

    def get_alert(self, alert_id: str) -> Alert | None:
        """Get an alert by ID."""
        return self._alerts.get(alert_id)

    def get_active_alerts(self) -> list[Alert]:
        """Get all active (firing) alerts."""
        return [a for a in self._alerts.values() if a.state == AlertState.FIRING]

    def get_all_alerts(self) -> list[Alert]:
        """Get all current alerts."""
        return list(self._alerts.values())

    def get_alert_history(
        self,
        limit: int = 100,
        severity: AlertSeverity | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[Alert]:
        """Get alert history."""
        history = self._alert_history.copy()

        if severity:
            history = [a for a in history if a.severity == severity]

        if start_time:
            history = [a for a in history if a.started_at >= start_time]

        if end_time:
            history = [a for a in history if a.started_at <= end_time]

        # Sort by start time descending
        history.sort(key=lambda a: a.started_at, reverse=True)

        # Trim history based on retention
        retention = timedelta(days=self._settings.alert_retention_days)
        cutoff = datetime.utcnow() - retention
        self._alert_history = [a for a in self._alert_history if a.started_at > cutoff]

        return history[:limit]

    async def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str,
    ) -> Alert | None:
        """Acknowledge an alert."""
        alert = self._alerts.get(alert_id)
        if not alert:
            return None

        alert.state = AlertState.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = acknowledged_by

        return alert

    async def resolve_alert(self, alert_id: str) -> Alert | None:
        """Manually resolve an alert."""
        alert = self._alerts.get(alert_id)
        if not alert:
            return None

        alert.state = AlertState.RESOLVED
        alert.resolved_at = datetime.utcnow()

        self._alert_history.append(alert)
        del self._alerts[alert_id]

        await self._notify_handlers(alert)

        return alert

    # ===========================================
    # SILENCING
    # ===========================================

    def create_silence(
        self,
        matchers: dict[str, str],
        duration_seconds: int,
        created_by: str,
        comment: str = "",
    ) -> str:
        """Create a silence to suppress alerts."""
        from uuid import uuid4
        silence_id = str(uuid4())

        self._silences[silence_id] = {
            "silence_id": silence_id,
            "matchers": matchers,
            "starts_at": datetime.utcnow(),
            "ends_at": datetime.utcnow() + timedelta(seconds=duration_seconds),
            "created_by": created_by,
            "comment": comment,
        }

        return silence_id

    def delete_silence(self, silence_id: str) -> bool:
        """Delete a silence."""
        if silence_id in self._silences:
            del self._silences[silence_id]
            return True
        return False

    def get_active_silences(self) -> list[dict[str, Any]]:
        """Get all active silences."""
        now = datetime.utcnow()
        active = []

        for silence_id, silence in list(self._silences.items()):
            if silence["ends_at"] < now:
                del self._silences[silence_id]
            else:
                active.append(silence)

        return active

    def _is_silenced(self, rule: AlertRule) -> bool:
        """Check if alerts for a rule are silenced."""
        now = datetime.utcnow()

        for silence in self._silences.values():
            if silence["ends_at"] < now:
                continue

            # Check if matchers match rule labels
            matchers = silence["matchers"]
            if all(rule.labels.get(k) == v for k, v in matchers.items()):
                return True

        return False

    # ===========================================
    # NOTIFICATIONS
    # ===========================================

    def register_handler(
        self,
        handler: Callable[[Alert], None],
    ) -> None:
        """Register a notification handler."""
        self._notification_handlers.append(handler)

    def unregister_handler(
        self,
        handler: Callable[[Alert], None],
    ) -> bool:
        """Unregister a notification handler."""
        if handler in self._notification_handlers:
            self._notification_handlers.remove(handler)
            return True
        return False

    async def _notify_handlers(self, alert: Alert) -> None:
        """Notify all registered handlers of an alert."""
        for handler in self._notification_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception:
                pass  # Don't let handler errors affect alerting

    # ===========================================
    # STATISTICS
    # ===========================================

    def get_stats(self) -> dict[str, Any]:
        """Get alerting statistics."""
        active = self.get_active_alerts()

        return {
            "total_rules": len(self._rules),
            "enabled_rules": sum(1 for r in self._rules.values() if r.enabled),
            "active_alerts": len(active),
            "critical_alerts": sum(1 for a in active if a.severity == AlertSeverity.CRITICAL),
            "warning_alerts": sum(1 for a in active if a.severity == AlertSeverity.WARNING),
            "info_alerts": sum(1 for a in active if a.severity == AlertSeverity.INFO),
            "acknowledged_alerts": sum(1 for a in self._alerts.values() if a.state == AlertState.ACKNOWLEDGED),
            "total_history": len(self._alert_history),
            "active_silences": len(self.get_active_silences()),
        }


# Singleton instance
_alert_manager: AlertManager | None = None


def get_alert_manager() -> AlertManager:
    """Get or create alert manager singleton."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


__all__ = [
    "AlertManager",
    "get_alert_manager",
]

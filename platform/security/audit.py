"""Audit Logging Service."""

from datetime import datetime, timedelta
from typing import Any, Callable

from platform.security.base import (
    AuditAction,
    AuditEntry,
    AuditResult,
)
from platform.security.config import AUDIT_EVENT_TYPES, get_settings


class AuditService:
    """Service for audit logging and compliance."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._entries: list[AuditEntry] = []
        self._handlers: list[Callable[[AuditEntry], None]] = []

    # ===========================================
    # AUDIT LOGGING
    # ===========================================

    async def log(
        self,
        event_type: str,
        action: AuditAction,
        result: AuditResult,
        user_id: str = "",
        username: str = "",
        resource_type: str = "",
        resource_id: str = "",
        ip_address: str = "",
        user_agent: str = "",
        request_id: str = "",
        details: dict[str, Any] | None = None,
        changes: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Create an audit log entry."""
        # Mask sensitive fields
        masked_details = self._mask_sensitive_data(details or {})
        masked_changes = self._mask_sensitive_data(changes or {})

        entry = AuditEntry(
            event_type=event_type,
            action=action,
            result=result,
            user_id=user_id,
            username=username,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            details=masked_details,
            changes=masked_changes,
        )

        self._entries.append(entry)

        # Notify handlers
        for handler in self._handlers:
            try:
                handler(entry)
            except Exception:
                pass

        # Cleanup old entries
        await self._cleanup_old_entries()

        return entry

    async def log_auth_event(
        self,
        event_type: str,
        result: AuditResult,
        user_id: str = "",
        username: str = "",
        ip_address: str = "",
        user_agent: str = "",
        details: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Log an authentication event."""
        action = AuditAction.LOGIN if "login" in event_type else AuditAction.LOGOUT
        return await self.log(
            event_type=event_type,
            action=action,
            result=result,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
        )

    async def log_access_event(
        self,
        resource_type: str,
        resource_id: str,
        action: AuditAction,
        result: AuditResult,
        user_id: str = "",
        username: str = "",
        ip_address: str = "",
        details: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Log a resource access event."""
        event_type = f"resource.{action.value}"
        return await self.log(
            event_type=event_type,
            action=action,
            result=result,
            user_id=user_id,
            username=username,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            details=details,
        )

    async def log_permission_event(
        self,
        event_type: str,
        user_id: str,
        username: str,
        resource: str,
        action_performed: str,
        result: AuditResult,
        ip_address: str = "",
        details: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Log a permission-related event."""
        audit_action = (
            AuditAction.GRANT if result == AuditResult.SUCCESS
            else AuditAction.DENY
        )
        return await self.log(
            event_type=event_type,
            action=audit_action,
            result=result,
            user_id=user_id,
            username=username,
            resource_type=resource,
            ip_address=ip_address,
            details={**(details or {}), "action": action_performed},
        )

    async def log_security_event(
        self,
        event_type: str,
        user_id: str = "",
        username: str = "",
        ip_address: str = "",
        details: dict[str, Any] | None = None,
    ) -> AuditEntry:
        """Log a security event."""
        return await self.log(
            event_type=event_type,
            action=AuditAction.DENY,
            result=AuditResult.DENIED,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            details=details,
        )

    async def log_data_change(
        self,
        resource_type: str,
        resource_id: str,
        action: AuditAction,
        user_id: str,
        username: str,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        ip_address: str = "",
    ) -> AuditEntry:
        """Log a data change event with before/after values."""
        changes = {}
        if before:
            changes["before"] = before
        if after:
            changes["after"] = after

        return await self.log(
            event_type=f"resource.{action.value}",
            action=action,
            result=AuditResult.SUCCESS,
            user_id=user_id,
            username=username,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            changes=changes,
        )

    def _mask_sensitive_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Mask sensitive fields in data."""
        if not data:
            return data

        masked = {}
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in self._settings.audit_sensitive_fields):
                masked[key] = "***MASKED***"
            elif isinstance(value, dict):
                masked[key] = self._mask_sensitive_data(value)
            else:
                masked[key] = value

        return masked

    async def _cleanup_old_entries(self) -> None:
        """Remove entries older than retention period."""
        retention = timedelta(days=self._settings.audit_retention_days)
        cutoff = datetime.utcnow() - retention

        self._entries = [
            e for e in self._entries
            if e.timestamp > cutoff
        ]

    # ===========================================
    # QUERYING
    # ===========================================

    async def get_entries(
        self,
        user_id: str | None = None,
        username: str | None = None,
        event_type: str | None = None,
        action: AuditAction | None = None,
        result: AuditResult | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        ip_address: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEntry]:
        """Get audit entries with filters."""
        entries = self._entries.copy()

        if user_id:
            entries = [e for e in entries if e.user_id == user_id]

        if username:
            entries = [e for e in entries if e.username == username]

        if event_type:
            entries = [e for e in entries if e.event_type == event_type]

        if action:
            entries = [e for e in entries if e.action == action]

        if result:
            entries = [e for e in entries if e.result == result]

        if resource_type:
            entries = [e for e in entries if e.resource_type == resource_type]

        if resource_id:
            entries = [e for e in entries if e.resource_id == resource_id]

        if ip_address:
            entries = [e for e in entries if e.ip_address == ip_address]

        if start_time:
            entries = [e for e in entries if e.timestamp >= start_time]

        if end_time:
            entries = [e for e in entries if e.timestamp <= end_time]

        # Sort by timestamp descending
        entries.sort(key=lambda e: e.timestamp, reverse=True)

        return entries[offset : offset + limit]

    async def get_entry(self, entry_id: str) -> AuditEntry | None:
        """Get a specific audit entry."""
        for entry in self._entries:
            if entry.entry_id == entry_id:
                return entry
        return None

    async def get_user_activity(
        self,
        user_id: str,
        days: int = 7,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Get recent activity for a user."""
        start_time = datetime.utcnow() - timedelta(days=days)
        return await self.get_entries(
            user_id=user_id,
            start_time=start_time,
            limit=limit,
        )

    async def get_resource_history(
        self,
        resource_type: str,
        resource_id: str,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Get audit history for a specific resource."""
        return await self.get_entries(
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit,
        )

    async def get_failed_logins(
        self,
        days: int = 1,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Get failed login attempts."""
        start_time = datetime.utcnow() - timedelta(days=days)
        return await self.get_entries(
            event_type="auth.login_failed",
            start_time=start_time,
            limit=limit,
        )

    async def get_security_events(
        self,
        days: int = 7,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Get security-related events."""
        start_time = datetime.utcnow() - timedelta(days=days)
        entries = await self.get_entries(
            start_time=start_time,
            limit=limit * 2,  # Fetch more to filter
        )

        # Filter for security events
        security_types = ["auth.login_failed", "security.violation", "security.rate_limited", "permission.denied"]
        return [e for e in entries if e.event_type in security_types or e.result == AuditResult.DENIED][:limit]

    # ===========================================
    # STATISTICS AND REPORTING
    # ===========================================

    async def get_stats(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Get audit statistics."""
        entries = self._entries.copy()

        if start_time:
            entries = [e for e in entries if e.timestamp >= start_time]

        if end_time:
            entries = [e for e in entries if e.timestamp <= end_time]

        # Count by event type
        by_event_type: dict[str, int] = {}
        for entry in entries:
            by_event_type[entry.event_type] = by_event_type.get(entry.event_type, 0) + 1

        # Count by action
        by_action: dict[str, int] = {}
        for entry in entries:
            action_name = entry.action.value
            by_action[action_name] = by_action.get(action_name, 0) + 1

        # Count by result
        by_result: dict[str, int] = {}
        for entry in entries:
            result_name = entry.result.value
            by_result[result_name] = by_result.get(result_name, 0) + 1

        # Count by user
        by_user: dict[str, int] = {}
        for entry in entries:
            if entry.username:
                by_user[entry.username] = by_user.get(entry.username, 0) + 1

        # Count by resource type
        by_resource: dict[str, int] = {}
        for entry in entries:
            if entry.resource_type:
                by_resource[entry.resource_type] = by_resource.get(entry.resource_type, 0) + 1

        return {
            "total_entries": len(entries),
            "by_event_type": by_event_type,
            "by_action": by_action,
            "by_result": by_result,
            "by_user": dict(sorted(by_user.items(), key=lambda x: x[1], reverse=True)[:10]),
            "by_resource": by_resource,
            "failed_operations": by_result.get("failure", 0) + by_result.get("denied", 0),
            "success_rate": (
                by_result.get("success", 0) / len(entries) * 100
                if entries else 0
            ),
        }

    async def generate_compliance_report(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, Any]:
        """Generate a compliance report for a time period."""
        entries = await self.get_entries(
            start_time=start_time,
            end_time=end_time,
            limit=100000,
        )

        # Group by day
        daily_activity: dict[str, int] = {}
        for entry in entries:
            day = entry.timestamp.strftime("%Y-%m-%d")
            daily_activity[day] = daily_activity.get(day, 0) + 1

        # Identify anomalies (days with unusually high/low activity)
        if daily_activity:
            avg_daily = sum(daily_activity.values()) / len(daily_activity)
            anomalies = {
                day: count for day, count in daily_activity.items()
                if count > avg_daily * 2 or count < avg_daily * 0.5
            }
        else:
            anomalies = {}

        stats = await self.get_stats(start_time, end_time)

        return {
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "summary": stats,
            "daily_activity": daily_activity,
            "anomalies": anomalies,
            "security_events": await self.get_security_events(
                days=int((end_time - start_time).days) + 1
            ),
        }

    # ===========================================
    # HANDLERS
    # ===========================================

    def register_handler(self, handler: Callable[[AuditEntry], None]) -> None:
        """Register an audit event handler."""
        self._handlers.append(handler)

    def unregister_handler(self, handler: Callable[[AuditEntry], None]) -> bool:
        """Unregister an audit event handler."""
        if handler in self._handlers:
            self._handlers.remove(handler)
            return True
        return False

    async def export_entries(
        self,
        format: str = "json",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> str:
        """Export audit entries."""
        import json

        entries = await self.get_entries(
            start_time=start_time,
            end_time=end_time,
            limit=100000,
        )

        if format == "json":
            return json.dumps([e.to_dict() for e in entries], indent=2)
        elif format == "csv":
            lines = ["entry_id,timestamp,event_type,action,result,user_id,username,resource_type,resource_id,ip_address"]
            for e in entries:
                lines.append(
                    f"{e.entry_id},{e.timestamp.isoformat()},{e.event_type},"
                    f"{e.action.value},{e.result.value},{e.user_id},{e.username},"
                    f"{e.resource_type},{e.resource_id},{e.ip_address}"
                )
            return "\n".join(lines)
        else:
            raise ValueError(f"Unsupported format: {format}")


# Singleton instance
_audit_service: AuditService | None = None


def get_audit_service() -> AuditService:
    """Get or create audit service singleton."""
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditService()
    return _audit_service


__all__ = [
    "AuditService",
    "get_audit_service",
]

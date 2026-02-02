"""Health Check System."""

import asyncio
import time
from datetime import datetime
from typing import Any, Callable

from platform.monitoring.base import (
    HealthCheck,
    HealthCheckResult,
    HealthStatus,
    ServiceHealth,
)
from platform.monitoring.config import MONITORED_SERVICES, get_settings


class HealthCheckService:
    """Service for managing health checks."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._checks: dict[str, HealthCheck] = {}
        self._services: dict[str, ServiceHealth] = {}
        self._check_history: dict[str, list[HealthCheckResult]] = {}
        self._start_time = datetime.utcnow()
        self._running = False
        self._task: asyncio.Task | None = None

        self._init_services()

    def _init_services(self) -> None:
        """Initialize monitored services."""
        for service_name in MONITORED_SERVICES:
            self._services[service_name] = ServiceHealth(
                service_name=service_name,
                status=HealthStatus.UNKNOWN,
            )

    async def start(self) -> None:
        """Start the health check background task."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._run_checks_loop())

    async def stop(self) -> None:
        """Stop the health check background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_checks_loop(self) -> None:
        """Run health checks in a loop."""
        while self._running:
            try:
                await self.run_all_checks()
                await asyncio.sleep(self._settings.health_check_interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(5)  # Brief pause on error

    # ===========================================
    # HEALTH CHECK REGISTRATION
    # ===========================================

    def register_check(
        self,
        name: str,
        check_fn: Callable[[], HealthCheckResult],
        check_type: str = "custom",
        service: str = "",
        interval_seconds: int | None = None,
        timeout_seconds: int | None = None,
        description: str = "",
    ) -> HealthCheck:
        """Register a health check."""
        check = HealthCheck(
            name=name,
            description=description,
            check_type=check_type,
            check_fn=check_fn,
            interval_seconds=interval_seconds or self._settings.health_check_interval_seconds,
            timeout_seconds=timeout_seconds or self._settings.health_check_timeout_seconds,
        )

        self._checks[check.check_id] = check
        self._check_history[check.check_id] = []

        # Associate with service
        if service and service in self._services:
            self._services[service].checks.append(check)

        return check

    def register_http_check(
        self,
        name: str,
        url: str,
        service: str = "",
        expected_status: int = 200,
        timeout_seconds: int | None = None,
    ) -> HealthCheck:
        """Register an HTTP health check."""
        async def check_http() -> HealthCheckResult:
            start = time.time()
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    timeout = aiohttp.ClientTimeout(
                        total=timeout_seconds or self._settings.health_check_timeout_seconds
                    )
                    async with session.get(url, timeout=timeout) as response:
                        duration_ms = (time.time() - start) * 1000

                        if response.status == expected_status:
                            return HealthCheckResult(
                                status=HealthStatus.HEALTHY,
                                message=f"HTTP {response.status}",
                                duration_ms=duration_ms,
                            )
                        else:
                            return HealthCheckResult(
                                status=HealthStatus.UNHEALTHY,
                                message=f"Unexpected status: {response.status}",
                                duration_ms=duration_ms,
                            )
            except Exception as e:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                    duration_ms=(time.time() - start) * 1000,
                )

        # Create sync wrapper
        def sync_check() -> HealthCheckResult:
            try:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(check_http())
            except RuntimeError:
                # No event loop, create one
                return asyncio.run(check_http())

        return self.register_check(
            name=name,
            check_fn=sync_check,
            check_type="http",
            service=service,
            timeout_seconds=timeout_seconds,
            description=f"HTTP check for {url}",
        )

    def register_tcp_check(
        self,
        name: str,
        host: str,
        port: int,
        service: str = "",
        timeout_seconds: int | None = None,
    ) -> HealthCheck:
        """Register a TCP health check."""
        async def check_tcp() -> HealthCheckResult:
            start = time.time()
            try:
                timeout = timeout_seconds or self._settings.health_check_timeout_seconds
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(host, port),
                    timeout=timeout,
                )
                writer.close()
                await writer.wait_closed()

                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    message=f"TCP connection successful",
                    duration_ms=(time.time() - start) * 1000,
                    details={"host": host, "port": port},
                )
            except Exception as e:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                    duration_ms=(time.time() - start) * 1000,
                )

        def sync_check() -> HealthCheckResult:
            try:
                loop = asyncio.get_event_loop()
                return loop.run_until_complete(check_tcp())
            except RuntimeError:
                return asyncio.run(check_tcp())

        check = self.register_check(
            name=name,
            check_fn=sync_check,
            check_type="tcp",
            service=service,
            timeout_seconds=timeout_seconds,
            description=f"TCP check for {host}:{port}",
        )
        check.target = f"{host}:{port}"

        return check

    def register_dependency_check(
        self,
        name: str,
        dependent_service: str,
        service: str = "",
    ) -> HealthCheck:
        """Register a dependency health check."""
        def check_dependency() -> HealthCheckResult:
            dep_service = self._services.get(dependent_service)
            if not dep_service:
                return HealthCheckResult(
                    status=HealthStatus.UNKNOWN,
                    message=f"Dependency {dependent_service} not found",
                )

            if dep_service.status == HealthStatus.HEALTHY:
                return HealthCheckResult(
                    status=HealthStatus.HEALTHY,
                    message=f"Dependency {dependent_service} is healthy",
                )
            else:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message=f"Dependency {dependent_service} is {dep_service.status.value}",
                )

        check = self.register_check(
            name=name,
            check_fn=check_dependency,
            check_type="dependency",
            service=service,
            description=f"Dependency check for {dependent_service}",
        )
        check.target = dependent_service

        # Track dependency relationship
        if service in self._services:
            self._services[service].dependencies.append(dependent_service)

        return check

    def unregister_check(self, check_id: str) -> bool:
        """Unregister a health check."""
        if check_id not in self._checks:
            return False

        check = self._checks.pop(check_id)

        # Remove from services
        for service in self._services.values():
            service.checks = [c for c in service.checks if c.check_id != check_id]

        # Remove history
        self._check_history.pop(check_id, None)

        return True

    # ===========================================
    # HEALTH CHECK EXECUTION
    # ===========================================

    async def run_check(self, check_id: str) -> HealthCheckResult:
        """Run a specific health check."""
        check = self._checks.get(check_id)
        if not check or not check.check_fn:
            return HealthCheckResult(
                status=HealthStatus.UNKNOWN,
                message="Check not found or has no function",
            )

        start = time.time()
        try:
            # Run check with timeout
            if asyncio.iscoroutinefunction(check.check_fn):
                result = await asyncio.wait_for(
                    check.check_fn(),
                    timeout=check.timeout_seconds,
                )
            else:
                result = await asyncio.wait_for(
                    asyncio.to_thread(check.check_fn),
                    timeout=check.timeout_seconds,
                )

            # Update consecutive counts
            if result.status == HealthStatus.HEALTHY:
                check.consecutive_successes += 1
                check.consecutive_failures = 0
            else:
                check.consecutive_failures += 1
                check.consecutive_successes = 0

        except asyncio.TimeoutError:
            result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message="Check timed out",
                duration_ms=(time.time() - start) * 1000,
            )
            check.consecutive_failures += 1
            check.consecutive_successes = 0

        except Exception as e:
            result = HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                duration_ms=(time.time() - start) * 1000,
            )
            check.consecutive_failures += 1
            check.consecutive_successes = 0

        # Store result
        check.last_result = result
        self._check_history[check_id].append(result)

        # Trim history
        max_history = 100
        if len(self._check_history[check_id]) > max_history:
            self._check_history[check_id] = self._check_history[check_id][-max_history:]

        return result

    async def run_all_checks(self) -> dict[str, HealthCheckResult]:
        """Run all enabled health checks."""
        results = {}

        for check_id, check in self._checks.items():
            if check.enabled:
                results[check_id] = await self.run_check(check_id)

        # Update service statuses
        self._update_service_statuses()

        return results

    async def run_service_checks(self, service_name: str) -> dict[str, HealthCheckResult]:
        """Run all health checks for a specific service."""
        service = self._services.get(service_name)
        if not service:
            return {}

        results = {}
        for check in service.checks:
            if check.enabled:
                results[check.check_id] = await self.run_check(check.check_id)

        self._update_service_status(service_name)
        return results

    def _update_service_statuses(self) -> None:
        """Update health status for all services."""
        for service_name in self._services:
            self._update_service_status(service_name)

    def _update_service_status(self, service_name: str) -> None:
        """Update health status for a specific service."""
        service = self._services.get(service_name)
        if not service:
            return

        if not service.checks:
            service.status = HealthStatus.UNKNOWN
            return

        # Determine overall status
        statuses = [c.last_result.status for c in service.checks if c.last_result]

        if not statuses:
            service.status = HealthStatus.UNKNOWN
        elif all(s == HealthStatus.HEALTHY for s in statuses):
            service.status = HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            # Check thresholds
            unhealthy_count = sum(
                1 for c in service.checks
                if c.consecutive_failures >= self._settings.unhealthy_threshold
            )
            if unhealthy_count > 0:
                service.status = HealthStatus.UNHEALTHY
            else:
                service.status = HealthStatus.DEGRADED
        else:
            service.status = HealthStatus.DEGRADED

        service.last_check = datetime.utcnow()
        service.uptime_seconds = (datetime.utcnow() - self._start_time).total_seconds()

    # ===========================================
    # LIVENESS AND READINESS
    # ===========================================

    async def liveness(self) -> HealthCheckResult:
        """Check if the service is alive (basic health)."""
        return HealthCheckResult(
            status=HealthStatus.HEALTHY,
            message="Service is alive",
            details={
                "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds(),
            },
        )

    async def readiness(self) -> HealthCheckResult:
        """Check if the service is ready to accept traffic."""
        # Check critical dependencies
        critical_services = ["database", "cache"]
        unhealthy_deps = []

        for service_name in critical_services:
            service = self._services.get(service_name)
            if service and service.status == HealthStatus.UNHEALTHY:
                unhealthy_deps.append(service_name)

        if unhealthy_deps:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Critical dependencies unhealthy: {', '.join(unhealthy_deps)}",
                details={"unhealthy_dependencies": unhealthy_deps},
            )

        return HealthCheckResult(
            status=HealthStatus.HEALTHY,
            message="Service is ready",
            details={
                "checked_services": critical_services,
            },
        )

    # ===========================================
    # QUERYING
    # ===========================================

    def get_check(self, check_id: str) -> HealthCheck | None:
        """Get a health check by ID."""
        return self._checks.get(check_id)

    def get_all_checks(self) -> list[HealthCheck]:
        """Get all registered health checks."""
        return list(self._checks.values())

    def get_service(self, service_name: str) -> ServiceHealth | None:
        """Get a service health status."""
        return self._services.get(service_name)

    def get_all_services(self) -> list[ServiceHealth]:
        """Get all service health statuses."""
        return list(self._services.values())

    def get_check_history(
        self,
        check_id: str,
        limit: int = 100,
    ) -> list[HealthCheckResult]:
        """Get health check history."""
        history = self._check_history.get(check_id, [])
        return history[-limit:]

    def get_overall_status(self) -> HealthStatus:
        """Get the overall system health status."""
        if not self._services:
            return HealthStatus.UNKNOWN

        statuses = [s.status for s in self._services.values()]

        if all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in statuses):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.UNKNOWN

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of health status."""
        services = self.get_all_services()

        return {
            "overall_status": self.get_overall_status().value,
            "total_services": len(services),
            "healthy_services": sum(1 for s in services if s.status == HealthStatus.HEALTHY),
            "unhealthy_services": sum(1 for s in services if s.status == HealthStatus.UNHEALTHY),
            "degraded_services": sum(1 for s in services if s.status == HealthStatus.DEGRADED),
            "unknown_services": sum(1 for s in services if s.status == HealthStatus.UNKNOWN),
            "total_checks": len(self._checks),
            "enabled_checks": sum(1 for c in self._checks.values() if c.enabled),
            "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds(),
            "last_check": datetime.utcnow().isoformat(),
        }


# Singleton instance
_health_service: HealthCheckService | None = None


def get_health_service() -> HealthCheckService:
    """Get or create health check service singleton."""
    global _health_service
    if _health_service is None:
        _health_service = HealthCheckService()
    return _health_service


__all__ = [
    "HealthCheckService",
    "get_health_service",
]

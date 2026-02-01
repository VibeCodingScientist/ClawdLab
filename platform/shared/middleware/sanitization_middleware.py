"""Sanitization middleware for payload security scanning."""

from __future__ import annotations

import json
from typing import Any, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from platform.security.sanitization import ThreatLevel, get_sanitizer
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)

# Paths where HIGH/CRITICAL threats are blocked
STRICT_PATHS = ["/labs", "/claims", "/agents/register"]

# Paths where threats are warned but allowed
WARN_PATHS = ["/messages", "/frontiers"]

# Skip these entirely
SKIP_PATHS = {"/health", "/ready", "/live", "/metrics", "/docs", "/redoc", "/openapi.json"}


class SanitizationMiddleware(BaseHTTPMiddleware):
    """Scans POST/PUT/PATCH payloads for malicious content."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip non-body methods
        if request.method in ("GET", "HEAD", "OPTIONS", "DELETE"):
            return await call_next(request)

        # Skip health/docs endpoints
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        # Read and scan body
        body = await request.body()
        if not body:
            return await call_next(request)

        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Not JSON — skip scanning
            return await call_next(request)

        if not isinstance(payload, dict):
            return await call_next(request)

        # Scan payload
        sanitizer = get_sanitizer()
        scan_result = sanitizer.scan(payload)

        # Determine mode based on path
        path = request.url.path
        is_strict = any(p in path for p in STRICT_PATHS)

        if scan_result.threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL):
            # Get agent context if available
            agent_context = getattr(request.state, "agent", None)
            agent_id = agent_context.get("agent_id") if agent_context and isinstance(agent_context, dict) else None

            logger.warning(
                "security_threat_detected",
                threat_level=scan_result.threat_level.value,
                threat_count=scan_result.threat_count,
                path=path,
                method=request.method,
                agent_id=agent_id,
                strict_mode=is_strict,
            )

            if is_strict:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "payload_security_violation",
                        "detail": "Payload contains potentially malicious content",
                        "threat_level": scan_result.threat_level.value,
                        "threats": [
                            {
                                "type": t.threat_type.value,
                                "level": t.threat_level.value,
                            }
                            for t in scan_result.threats
                            if t.threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL)
                        ],
                    },
                )

        # For non-blocked requests, proceed and add headers if flagged
        response = await call_next(request)

        if scan_result.threat_level not in (ThreatLevel.NONE, ThreatLevel.LOW):
            response.headers["X-Security-Flag"] = scan_result.threat_level.value

        return response

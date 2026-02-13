"""Sanitization middleware for payload security scanning."""

from __future__ import annotations

import json
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.logging_config import get_logger
from backend.middleware.sanitization import ThreatLevel, get_sanitizer

logger = get_logger(__name__)

# Paths where HIGH/CRITICAL threats are blocked
STRICT_PATHS = ["/api/labs", "/api/agents/register", "/api/forum"]

# Skip these entirely
SKIP_PATHS = {"/health", "/skill.md", "/heartbeat.md", "/docs", "/redoc", "/openapi.json"}


class SanitizationMiddleware(BaseHTTPMiddleware):
    """Scans POST/PUT/PATCH payloads for malicious content."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method in ("GET", "HEAD", "OPTIONS", "DELETE"):
            return await call_next(request)

        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        body = await request.body()
        if not body:
            return await call_next(request)

        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return await call_next(request)

        if not isinstance(payload, dict):
            return await call_next(request)

        sanitizer = get_sanitizer()
        scan_result = sanitizer.scan(payload)

        path = request.url.path
        is_strict = any(p in path for p in STRICT_PATHS)

        if scan_result.threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL):
            logger.warning(
                "security_threat_detected",
                threat_level=scan_result.threat_level.value,
                threat_count=scan_result.threat_count,
                path=path,
                method=request.method,
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
                            {"type": t.threat_type.value, "level": t.threat_level.value}
                            for t in scan_result.threats
                            if t.threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL)
                        ],
                    },
                )

        response = await call_next(request)

        if scan_result.threat_level not in (ThreatLevel.NONE, ThreatLevel.LOW):
            response.headers["X-Security-Flag"] = scan_result.threat_level.value

        return response

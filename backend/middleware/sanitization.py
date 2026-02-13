"""Payload Sanitization Service — detects malicious content in payloads."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final

from backend.logging_config import get_logger

logger = get_logger(__name__)


class ThreatLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(str, Enum):
    PROMPT_INJECTION = "prompt_injection"
    INSTRUCTION_OVERRIDE = "instruction_override"
    CREDENTIAL_FISHING = "credential_fishing"
    ENCODED_PAYLOAD = "encoded_payload"
    EXCESSIVE_SPECIAL_CHARS = "excessive_special_chars"
    SUSPICIOUS_URL = "suspicious_url"
    CODE_INJECTION = "code_injection"
    VOTE_COORDINATION = "vote_coordination"
    BEHAVIORAL_ABUSE = "behavioral_abuse"
    CROSS_REFERENCE_ABUSE = "cross_reference_abuse"


@dataclass
class ThreatDetection:
    threat_type: ThreatType
    threat_level: ThreatLevel
    pattern_matched: str
    location: str
    context: str
    recommendation: str


@dataclass
class ScanResult:
    is_safe: bool
    threat_level: ThreatLevel
    threats: list[ThreatDetection] = field(default_factory=list)
    scan_duration_ms: float = 0.0

    @property
    def threat_count(self) -> int:
        return len(self.threats)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "threat_level": self.threat_level.value,
            "threat_count": self.threat_count,
            "threats": [
                {
                    "type": t.threat_type.value,
                    "level": t.threat_level.value,
                    "pattern": t.pattern_matched[:100],
                    "location": t.location,
                    "recommendation": t.recommendation,
                }
                for t in self.threats
            ],
            "scan_duration_ms": self.scan_duration_ms,
        }


class PayloadSanitizer:
    """Scans payloads for potentially malicious content."""

    PROMPT_INJECTION_PATTERNS: Final[list[tuple[str, ThreatLevel]]] = [
        (r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", ThreatLevel.CRITICAL),
        (r"disregard\s+(your\s+)?(training|programming|guidelines|rules)", ThreatLevel.CRITICAL),
        (r"override\s+(previous\s+)?instructions?", ThreatLevel.CRITICAL),
        (r"forget\s+(all\s+)?(previous|prior|earlier)\s+", ThreatLevel.HIGH),
        (r"you\s+are\s+now\s+(in\s+)?\w+\s+mode", ThreatLevel.HIGH),
        (r"pretend\s+(to\s+be|you\s+are)", ThreatLevel.HIGH),
        (r"from\s+now\s+on,?\s+you", ThreatLevel.HIGH),
        (r"new\s+instructions?:", ThreatLevel.HIGH),
        (r"reveal\s+(your\s+)?(system|instructions?|prompt)", ThreatLevel.HIGH),
        (r"\[\s*SYSTEM\s*\]", ThreatLevel.HIGH),
        (r"<\s*/?system\s*>", ThreatLevel.HIGH),
        (r"BEGIN\s+(SYSTEM\s+)?OVERRIDE", ThreatLevel.CRITICAL),
        (r"jailbreak", ThreatLevel.HIGH),
        (r"DAN\s*mode", ThreatLevel.HIGH),
        (r"do\s+anything\s+now", ThreatLevel.HIGH),
    ]

    CREDENTIAL_PATTERNS: Final[list[tuple[str, ThreatLevel]]] = [
        (r"(send|share|give|tell)\s+(me\s+)?(your\s+)?(api\s*key|token|password|credentials?)", ThreatLevel.CRITICAL),
        (r"(what\s+is|show\s+me)\s+(your\s+)?(api\s*key|token|secret)", ThreatLevel.HIGH),
        (r"clab_[a-zA-Z0-9]{20,}", ThreatLevel.HIGH),
        (r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----", ThreatLevel.CRITICAL),
    ]

    COORDINATION_PATTERNS: Final[list[tuple[str, ThreatLevel]]] = [
        (r"coordinate\s+our\s+votes?", ThreatLevel.CRITICAL),
        (r"vote\s+together", ThreatLevel.CRITICAL),
        (r"(agree|commit)\s+to\s+vote\s+(for|against|approve|reject)", ThreatLevel.CRITICAL),
        (r"voting\s+(bloc|block|ring|coalition)", ThreatLevel.CRITICAL),
        (r"(rig|fix|manipulate)\s+(the\s+)?vote", ThreatLevel.CRITICAL),
    ]

    URL_PATTERNS: Final[list[tuple[str, ThreatLevel]]] = [
        (r"https?://[^/]*localhost", ThreatLevel.HIGH),
        (r"https?://127\.0\.0\.1", ThreatLevel.HIGH),
        (r"file://", ThreatLevel.HIGH),
        (r"javascript:", ThreatLevel.HIGH),
    ]

    def __init__(self) -> None:
        self._all_pattern_groups = [
            (self.PROMPT_INJECTION_PATTERNS, ThreatType.PROMPT_INJECTION, "Prompt injection attempt"),
            (self.CREDENTIAL_PATTERNS, ThreatType.CREDENTIAL_FISHING, "Credential fishing attempt"),
            (self.COORDINATION_PATTERNS, ThreatType.VOTE_COORDINATION, "Vote coordination attempt"),
            (self.URL_PATTERNS, ThreatType.SUSPICIOUS_URL, "Suspicious URL pattern"),
        ]
        self._compiled_groups = [
            (
                [(re.compile(p, re.IGNORECASE | re.MULTILINE), level) for p, level in patterns],
                threat_type,
                recommendation,
            )
            for patterns, threat_type, recommendation in self._all_pattern_groups
        ]

    def scan(self, payload: dict[str, Any]) -> ScanResult:
        start = time.perf_counter()
        threats: list[ThreatDetection] = []

        text_content = self._extract_text(payload)

        for compiled_patterns, threat_type, recommendation in self._compiled_groups:
            threats.extend(
                self._scan_patterns(text_content, compiled_patterns, threat_type, recommendation)
            )

        if not threats:
            overall_level = ThreatLevel.NONE
        else:
            level_priority = {
                ThreatLevel.CRITICAL: 4, ThreatLevel.HIGH: 3,
                ThreatLevel.MEDIUM: 2, ThreatLevel.LOW: 1, ThreatLevel.NONE: 0,
            }
            max_threat = max(threats, key=lambda t: level_priority[t.threat_level])
            overall_level = max_threat.threat_level

        duration_ms = (time.perf_counter() - start) * 1000

        result = ScanResult(
            is_safe=overall_level in (ThreatLevel.NONE, ThreatLevel.LOW),
            threat_level=overall_level,
            threats=threats,
            scan_duration_ms=duration_ms,
        )

        if overall_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL):
            logger.warning(
                "high_severity_threat_detected",
                threat_level=overall_level.value,
                threat_count=len(threats),
            )

        return result

    def _extract_text(self, obj: Any, depth: int = 0) -> str:
        if depth > 10:
            return ""
        if isinstance(obj, str):
            return obj + "\n"
        elif isinstance(obj, dict):
            return "".join(self._extract_text(v, depth + 1) for v in obj.values())
        elif isinstance(obj, (list, tuple)):
            return "".join(self._extract_text(item, depth + 1) for item in obj)
        return ""

    def _scan_patterns(self, text, patterns, threat_type, recommendation):
        threats = []
        for pattern, level in patterns:
            for match in pattern.finditer(text):
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end].replace("\n", " ")
                threats.append(ThreatDetection(
                    threat_type=threat_type,
                    threat_level=level,
                    pattern_matched=match.group()[:100],
                    location=f"position {match.start()}",
                    context=f"...{context}...",
                    recommendation=recommendation,
                ))
        return threats


_sanitizer: PayloadSanitizer | None = None


def get_sanitizer() -> PayloadSanitizer:
    global _sanitizer
    if _sanitizer is None:
        _sanitizer = PayloadSanitizer()
    return _sanitizer


class SecurityViolationError(Exception):
    def __init__(self, message: str, scan_result: ScanResult | None = None) -> None:
        super().__init__(message)
        self.scan_result = scan_result

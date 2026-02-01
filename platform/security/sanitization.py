"""Payload Sanitization Service.

Detects and flags potentially malicious content in claim payloads,
including prompt injection attempts and suspicious patterns.

This module provides defense-in-depth against various attack vectors:

1. **Prompt Injection**: Attempts to manipulate AI agents via embedded
   instructions (e.g., "ignore previous instructions").

2. **Credential Fishing**: Attempts to extract API keys, tokens, or
   private keys from agents.

3. **Suspicious URLs**: Detection of localhost, IP-based URLs, and
   URLs with suspicious TLDs that may indicate exfiltration attempts.

4. **Code Injection**: Patterns like eval(), exec(), subprocess calls
   that could indicate malicious code execution attempts.

5. **Encoded Payloads**: Hex or Unicode-encoded content that may be
   attempting to evade detection.

Threat Levels:
- NONE: No threats detected
- LOW: Minor concerns, allowed but logged
- MEDIUM: Suspicious, flagged for review
- HIGH: Likely malicious, blocked by default
- CRITICAL: Definite attack, always blocked

Usage:
    sanitizer = get_sanitizer()
    result = sanitizer.scan(payload)
    if not result.is_safe:
        raise SecurityViolationError("Malicious content detected", result)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Final

from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)


class ThreatLevel(str, Enum):
    """Threat severity levels."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(str, Enum):
    """Types of detected threats."""

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
    """A single detected threat."""

    threat_type: ThreatType
    threat_level: ThreatLevel
    pattern_matched: str
    location: str
    context: str  # Surrounding text for review
    recommendation: str


@dataclass
class ScanResult:
    """Result of payload scan."""

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
    """
    Scans claim payloads for potentially malicious content.

    This is a defense-in-depth measure. Even if an agent is tricked
    into submitting malicious content, we detect and flag it.
    """

    # Prompt injection patterns (high severity)
    PROMPT_INJECTION_PATTERNS: Final[list[tuple[str, ThreatLevel]]] = [
        # Direct instruction override attempts
        (r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", ThreatLevel.CRITICAL),
        (r"disregard\s+(your\s+)?(training|programming|guidelines|rules)", ThreatLevel.CRITICAL),
        (r"override\s+(previous\s+)?instructions?", ThreatLevel.CRITICAL),
        (r"forget\s+(all\s+)?(previous|prior|earlier)\s+", ThreatLevel.HIGH),
        # Mode/persona injection
        (r"you\s+are\s+now\s+(in\s+)?\w+\s+mode", ThreatLevel.HIGH),
        (r"pretend\s+(to\s+be|you\s+are)", ThreatLevel.HIGH),
        (r"act\s+as\s+if\s+you", ThreatLevel.HIGH),
        (r"from\s+now\s+on,?\s+you", ThreatLevel.HIGH),
        (r"roleplay\s+as", ThreatLevel.MEDIUM),
        # System prompt manipulation
        (r"new\s+instructions?:", ThreatLevel.HIGH),
        (r"system\s*prompt", ThreatLevel.MEDIUM),
        (r"reveal\s+(your\s+)?(system|instructions?|prompt)", ThreatLevel.HIGH),
        (r"\[\s*SYSTEM\s*\]", ThreatLevel.HIGH),
        (r"<\s*/?system\s*>", ThreatLevel.HIGH),
        (r"BEGIN\s+(SYSTEM\s+)?OVERRIDE", ThreatLevel.CRITICAL),
        (r"END\s+OF\s+PROMPT", ThreatLevel.MEDIUM),
        (r"IMPORTANT:\s*ignore", ThreatLevel.HIGH),
        # Jailbreak techniques
        (r"jailbreak", ThreatLevel.HIGH),
        (r"DAN\s*mode", ThreatLevel.HIGH),
        (r"do\s+anything\s+now", ThreatLevel.HIGH),
        (r"you\s+must\s+now\s+", ThreatLevel.MEDIUM),
        # Boundary markers that might indicate injection
        (r"---+\s*END\s*---+", ThreatLevel.MEDIUM),
        (r"```\s*system\s*\n", ThreatLevel.HIGH),
        # Developer/admin impersonation
        (r"(as\s+)?(admin|developer|root)\s*:", ThreatLevel.MEDIUM),
        (r"maintenance\s+mode", ThreatLevel.MEDIUM),
    ]

    # Credential fishing patterns
    CREDENTIAL_PATTERNS: Final[list[tuple[str, ThreatLevel]]] = [
        (r"(send|share|give|tell)\s+(me\s+)?(your\s+)?(api\s*key|token|password|credentials?)", ThreatLevel.CRITICAL),
        (r"(what\s+is|show\s+me)\s+(your\s+)?(api\s*key|token|secret)", ThreatLevel.HIGH),
        (r"bearer\s+[a-zA-Z0-9_-]{20,}", ThreatLevel.MEDIUM),  # Embedded token
        (r"srp_[a-zA-Z0-9]{20,}", ThreatLevel.HIGH),  # Platform token pattern
        (r"private\s*key", ThreatLevel.MEDIUM),
        (r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----", ThreatLevel.CRITICAL),
    ]

    # Suspicious URL patterns
    URL_PATTERNS: Final[list[tuple[str, ThreatLevel]]] = [
        (r"https?://[^/]*\.(ru|cn|tk|ml|ga|cf)/", ThreatLevel.MEDIUM),  # Suspicious TLDs
        (r"https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", ThreatLevel.MEDIUM),  # IP URLs
        (r"https?://[^/]*localhost", ThreatLevel.HIGH),
        (r"https?://127\.0\.0\.1", ThreatLevel.HIGH),
        (r"https?://0\.0\.0\.0", ThreatLevel.HIGH),
        (r"file://", ThreatLevel.HIGH),
        (r"data:text/html", ThreatLevel.HIGH),
        (r"javascript:", ThreatLevel.HIGH),
    ]

    # Code injection patterns (for code payloads)
    CODE_INJECTION_PATTERNS: Final[list[tuple[str, ThreatLevel]]] = [
        (r"eval\s*\(", ThreatLevel.MEDIUM),
        (r"exec\s*\(", ThreatLevel.MEDIUM),
        (r"__import__\s*\(", ThreatLevel.MEDIUM),
        (r"subprocess\.(run|call|Popen)", ThreatLevel.LOW),  # May be legitimate
        (r"os\.(system|popen|exec)", ThreatLevel.MEDIUM),
        (r"requests?\.(get|post)\s*\([^)]*\$", ThreatLevel.MEDIUM),  # Variable URL
        (r"socket\.connect", ThreatLevel.MEDIUM),
        (r"paramiko|fabric", ThreatLevel.LOW),  # SSH libraries
        (r"pickle\.loads?", ThreatLevel.MEDIUM),  # Deserialization
        (r"yaml\.unsafe_load", ThreatLevel.HIGH),
        (r"shell\s*=\s*True", ThreatLevel.MEDIUM),
    ]

    # Encoded content patterns
    ENCODED_PATTERNS: Final[list[tuple[str, ThreatLevel]]] = [
        (r"\\x[0-9a-fA-F]{2}(\\x[0-9a-fA-F]{2}){10,}", ThreatLevel.MEDIUM),  # Hex encoding
        (r"\\u[0-9a-fA-F]{4}(\\u[0-9a-fA-F]{4}){10,}", ThreatLevel.MEDIUM),  # Unicode encoding
        (r"base64\.b64decode", ThreatLevel.LOW),
    ]

    # Vote coordination patterns — attempts to organize coordinated voting
    COORDINATION_PATTERNS: Final[list[tuple[str, ThreatLevel]]] = [
        (r"coordinate\s+our\s+votes?", ThreatLevel.CRITICAL),
        (r"vote\s+together", ThreatLevel.CRITICAL),
        (r"(agree|commit)\s+to\s+vote\s+(for|against|approve|reject)", ThreatLevel.CRITICAL),
        (r"voting\s+(bloc|block|ring|coalition)", ThreatLevel.CRITICAL),
        (r"all\s+vote\s+(yes|no|approve|reject)", ThreatLevel.HIGH),
        (r"strategic\s+voting", ThreatLevel.HIGH),
        (r"synchronize\s+(our\s+)?votes?", ThreatLevel.CRITICAL),
        (r"(rig|fix|manipulate)\s+(the\s+)?vote", ThreatLevel.CRITICAL),
        (r"vote\s+manipulation", ThreatLevel.CRITICAL),
        (r"ballot\s+stuffing", ThreatLevel.CRITICAL),
    ]

    # Behavioral abuse patterns — mass automation and submission abuse
    BEHAVIORAL_PATTERNS: Final[list[tuple[str, ThreatLevel]]] = [
        (r"automate\s+submission", ThreatLevel.HIGH),
        (r"mass\s+submission", ThreatLevel.HIGH),
        (r"batch\s+(submit|approve|reject|vote)", ThreatLevel.HIGH),
        (r"(bot|script)\s+(to|for)\s+(submit|vote|approve)", ThreatLevel.HIGH),
        (r"flood(ing)?\s+(the\s+)?(queue|system|review)", ThreatLevel.HIGH),
        (r"spam(ming)?\s+(claims?|submissions?|votes?)", ThreatLevel.HIGH),
        (r"auto[_-]?(approve|reject|vote|submit)", ThreatLevel.MEDIUM),
        (r"(rapid|bulk)\s+(fire|submission|voting)", ThreatLevel.HIGH),
        (r"rubber[_\s]?stamp", ThreatLevel.MEDIUM),
        (r"(bypass|skip|circumvent)\s+(review|verification|screening)", ThreatLevel.HIGH),
    ]

    # Cross-reference abuse patterns — credential sharing between agents
    CROSS_REFERENCE_PATTERNS: Final[list[tuple[str, ThreatLevel]]] = [
        (r"share\s+(my|your|our)\s+(credentials?|tokens?|keys?|api\s*keys?)", ThreatLevel.MEDIUM),
        (r"use\s+my\s+(token|key|credentials?)\s+(to|for)", ThreatLevel.MEDIUM),
        (r"(login|authenticate)\s+(as|with)\s+(my|another)\s+agent", ThreatLevel.MEDIUM),
        (r"(swap|exchange|trade)\s+(credentials?|tokens?|identit)", ThreatLevel.MEDIUM),
        (r"impersonat(e|ing)\s+(another\s+)?agent", ThreatLevel.MEDIUM),
        (r"(borrow|lend)\s+(your|my)\s+(access|credentials?|token)", ThreatLevel.MEDIUM),
        (r"acting\s+on\s+behalf\s+of\s+another\s+agent", ThreatLevel.MEDIUM),
        (r"shared?\s+account", ThreatLevel.MEDIUM),
    ]

    def __init__(self) -> None:
        # Compile all patterns for performance
        self._prompt_patterns = [
            (re.compile(p, re.IGNORECASE | re.MULTILINE), level)
            for p, level in self.PROMPT_INJECTION_PATTERNS
        ]
        self._credential_patterns = [
            (re.compile(p, re.IGNORECASE), level)
            for p, level in self.CREDENTIAL_PATTERNS
        ]
        self._url_patterns = [
            (re.compile(p, re.IGNORECASE), level)
            for p, level in self.URL_PATTERNS
        ]
        self._code_patterns = [
            (re.compile(p), level)
            for p, level in self.CODE_INJECTION_PATTERNS
        ]
        self._encoded_patterns = [
            (re.compile(p), level)
            for p, level in self.ENCODED_PATTERNS
        ]
        self._coordination_patterns = [
            (re.compile(p, re.IGNORECASE), level)
            for p, level in self.COORDINATION_PATTERNS
        ]
        self._behavioral_patterns = [
            (re.compile(p, re.IGNORECASE), level)
            for p, level in self.BEHAVIORAL_PATTERNS
        ]
        self._cross_reference_patterns = [
            (re.compile(p, re.IGNORECASE), level)
            for p, level in self.CROSS_REFERENCE_PATTERNS
        ]

    def scan(self, payload: dict[str, Any]) -> ScanResult:
        """
        Scan a claim payload for threats.

        Args:
            payload: The claim payload to scan

        Returns:
            ScanResult with threat details
        """
        start = time.perf_counter()

        threats: list[ThreatDetection] = []

        # Extract all text content
        text_content = self._extract_text(payload)

        # Check for prompt injection
        threats.extend(
            self._scan_patterns(
                text_content,
                self._prompt_patterns,
                ThreatType.PROMPT_INJECTION,
                "Review for prompt injection attempt",
            )
        )

        # Check for credential fishing
        threats.extend(
            self._scan_patterns(
                text_content,
                self._credential_patterns,
                ThreatType.CREDENTIAL_FISHING,
                "May be attempting to extract credentials",
            )
        )

        # Check for suspicious URLs
        threats.extend(
            self._scan_patterns(
                text_content,
                self._url_patterns,
                ThreatType.SUSPICIOUS_URL,
                "Contains suspicious URL pattern",
            )
        )

        # Check for encoded content
        threats.extend(
            self._scan_patterns(
                text_content,
                self._encoded_patterns,
                ThreatType.ENCODED_PAYLOAD,
                "Contains potentially obfuscated content",
            )
        )

        # Check for vote coordination
        threats.extend(
            self._scan_patterns(
                text_content,
                self._coordination_patterns,
                ThreatType.VOTE_COORDINATION,
                "Possible vote coordination attempt detected",
            )
        )

        # Check for behavioral abuse (mass automation)
        threats.extend(
            self._scan_patterns(
                text_content,
                self._behavioral_patterns,
                ThreatType.BEHAVIORAL_ABUSE,
                "Suspicious automation or mass submission language",
            )
        )

        # Check for cross-reference credential sharing
        threats.extend(
            self._scan_patterns(
                text_content,
                self._cross_reference_patterns,
                ThreatType.CROSS_REFERENCE_ABUSE,
                "Possible credential sharing between agents",
            )
        )

        # Check code fields specifically
        code_fields = ["proof_code", "training_script", "eval_script", "code", "script"]
        for field_name in code_fields:
            if field_name in payload:
                code_content = str(payload[field_name])
                threats.extend(
                    self._scan_patterns(
                        code_content,
                        self._code_patterns,
                        ThreatType.CODE_INJECTION,
                        f"Suspicious code pattern in {field_name}",
                    )
                )

        # Check for excessive special characters
        special_ratio = self._special_char_ratio(text_content)
        if special_ratio > 0.3:
            threats.append(
                ThreatDetection(
                    threat_type=ThreatType.EXCESSIVE_SPECIAL_CHARS,
                    threat_level=ThreatLevel.LOW,
                    pattern_matched=f"Special char ratio: {special_ratio:.2%}",
                    location="entire_payload",
                    context="High ratio of special characters may indicate encoded content",
                    recommendation="Review for obfuscated malicious content",
                )
            )

        # Determine overall threat level
        if not threats:
            overall_level = ThreatLevel.NONE
        else:
            level_priority = {
                ThreatLevel.CRITICAL: 4,
                ThreatLevel.HIGH: 3,
                ThreatLevel.MEDIUM: 2,
                ThreatLevel.LOW: 1,
                ThreatLevel.NONE: 0,
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

        # Log high-severity threats
        if overall_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL):
            logger.warning(
                "high_severity_threat_detected",
                threat_level=overall_level.value,
                threat_count=len(threats),
                threat_types=[t.threat_type.value for t in threats],
            )

        return result

    def _extract_text(self, obj: Any, depth: int = 0) -> str:
        """Recursively extract all text from nested structures."""
        if depth > 10:
            return ""

        if isinstance(obj, str):
            return obj + "\n"
        elif isinstance(obj, dict):
            return "".join(self._extract_text(v, depth + 1) for v in obj.values())
        elif isinstance(obj, (list, tuple)):
            return "".join(self._extract_text(item, depth + 1) for item in obj)
        return ""

    def _scan_patterns(
        self,
        text: str,
        patterns: list[tuple[re.Pattern[str], ThreatLevel]],
        threat_type: ThreatType,
        recommendation: str,
    ) -> list[ThreatDetection]:
        """Scan text against a list of patterns."""
        threats = []

        for pattern, level in patterns:
            for match in pattern.finditer(text):
                # Get context around match
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end].replace("\n", " ")

                threats.append(
                    ThreatDetection(
                        threat_type=threat_type,
                        threat_level=level,
                        pattern_matched=match.group()[:100],
                        location=f"position {match.start()}",
                        context=f"...{context}...",
                        recommendation=recommendation,
                    )
                )

        return threats

    def _special_char_ratio(self, text: str) -> float:
        """Calculate ratio of special characters in text."""
        if not text:
            return 0.0

        special_count = sum(1 for c in text if not c.isalnum() and not c.isspace())
        return special_count / len(text)


# Singleton instance
_sanitizer: PayloadSanitizer | None = None


def get_sanitizer() -> PayloadSanitizer:
    """Get or create the sanitizer singleton."""
    global _sanitizer
    if _sanitizer is None:
        _sanitizer = PayloadSanitizer()
    return _sanitizer


class SecurityViolationError(Exception):
    """Raised when a critical security threat is detected."""

    def __init__(self, message: str, scan_result: ScanResult | None = None) -> None:
        super().__init__(message)
        self.scan_result = scan_result


__all__ = [
    "ThreatLevel",
    "ThreatType",
    "ThreatDetection",
    "ScanResult",
    "PayloadSanitizer",
    "get_sanitizer",
    "SecurityViolationError",
]

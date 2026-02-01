"""Claim routing service for directing claims to appropriate verification engines."""

import re
from typing import Any

from platform.orchestration.base import (
    Claim,
    ClaimStatus,
    RoutingDecision,
)
from platform.orchestration.config import (
    CLAIM_TYPE_DOMAINS,
    RESEARCH_DOMAINS,
    get_settings,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ClaimRouter:
    """
    Route claims to appropriate verification engines.

    Uses multiple strategies:
    1. Explicit claim type mapping
    2. Keyword-based domain detection
    3. File extension analysis
    4. Content analysis
    """

    def __init__(self):
        """Initialize claim router."""
        self._domain_keywords = {
            domain: set(config["keywords"])
            for domain, config in RESEARCH_DOMAINS.items()
        }
        self._domain_extensions = {
            domain: set(config["file_extensions"])
            for domain, config in RESEARCH_DOMAINS.items()
        }

    async def route_claim(self, claim: Claim) -> RoutingDecision:
        """
        Route a claim to the appropriate verification engine.

        Args:
            claim: The claim to route

        Returns:
            RoutingDecision with domain and engine assignment
        """
        # Strategy 1: Explicit claim type mapping
        if claim.claim_type and claim.claim_type in CLAIM_TYPE_DOMAINS:
            domain = CLAIM_TYPE_DOMAINS[claim.claim_type]
            return self._create_decision(claim, domain, confidence=1.0, reasoning="Explicit claim type mapping")

        # Strategy 2: Pre-specified domain
        if claim.domain and claim.domain in RESEARCH_DOMAINS:
            return self._create_decision(claim, claim.domain, confidence=0.95, reasoning="Pre-specified domain")

        # Strategy 3: Analyze content
        analysis = self._analyze_content(claim)

        if analysis["best_domain"] and analysis["confidence"] >= settings.min_routing_confidence:
            return self._create_decision(
                claim,
                analysis["best_domain"],
                confidence=analysis["confidence"],
                reasoning=analysis["reasoning"],
                alternatives=analysis["alternatives"],
            )

        # Strategy 4: File extension analysis
        if claim.metadata.get("files"):
            file_domain = self._analyze_files(claim.metadata["files"])
            if file_domain:
                return self._create_decision(
                    claim,
                    file_domain,
                    confidence=0.8,
                    reasoning="File extension analysis",
                )

        # Default: Return with low confidence for manual review
        return RoutingDecision(
            claim_id=claim.claim_id,
            domain="unknown",
            verification_engine="manual_review",
            celery_queue="research.manual",
            confidence=0.0,
            reasoning="Unable to automatically determine domain",
            alternative_domains=list(RESEARCH_DOMAINS.keys()),
        )

    def _create_decision(
        self,
        claim: Claim,
        domain: str,
        confidence: float,
        reasoning: str,
        alternatives: list[str] | None = None,
    ) -> RoutingDecision:
        """Create a routing decision."""
        config = RESEARCH_DOMAINS.get(domain, {})

        return RoutingDecision(
            claim_id=claim.claim_id,
            domain=domain,
            verification_engine=config.get("verification_engine", "unknown"),
            celery_queue=config.get("celery_queue", "verify.default"),
            confidence=confidence,
            reasoning=reasoning,
            alternative_domains=alternatives or [],
        )

    def _analyze_content(self, claim: Claim) -> dict[str, Any]:
        """Analyze claim content to determine domain."""
        content = f"{claim.content} {claim.claim_type}".lower()

        # Count keyword matches per domain
        domain_scores = {}
        for domain, keywords in self._domain_keywords.items():
            score = 0
            matched_keywords = []
            for keyword in keywords:
                if keyword.lower() in content:
                    score += 1
                    matched_keywords.append(keyword)
            if score > 0:
                domain_scores[domain] = {
                    "score": score,
                    "keywords": matched_keywords,
                }

        if not domain_scores:
            return {
                "best_domain": None,
                "confidence": 0.0,
                "reasoning": "No domain keywords found",
                "alternatives": [],
            }

        # Find best match
        sorted_domains = sorted(
            domain_scores.items(),
            key=lambda x: x[1]["score"],
            reverse=True,
        )

        best_domain, best_info = sorted_domains[0]
        max_keywords = len(self._domain_keywords[best_domain])
        confidence = min(0.95, best_info["score"] / max(3, max_keywords / 2))

        # Get alternatives
        alternatives = [d for d, _ in sorted_domains[1:3]]

        return {
            "best_domain": best_domain,
            "confidence": confidence,
            "reasoning": f"Matched keywords: {', '.join(best_info['keywords'])}",
            "alternatives": alternatives,
        }

    def _analyze_files(self, files: list[str]) -> str | None:
        """Determine domain from file extensions."""
        extension_counts = {}

        for file_path in files:
            ext = self._get_extension(file_path)
            for domain, extensions in self._domain_extensions.items():
                if ext in extensions:
                    extension_counts[domain] = extension_counts.get(domain, 0) + 1

        if extension_counts:
            return max(extension_counts.items(), key=lambda x: x[1])[0]
        return None

    def _get_extension(self, file_path: str) -> str:
        """Extract file extension."""
        parts = file_path.lower().split(".")
        if len(parts) > 1:
            return f".{parts[-1]}"
        return ""

    async def route_claims(self, claims: list[Claim]) -> list[RoutingDecision]:
        """
        Route multiple claims.

        Args:
            claims: List of claims to route

        Returns:
            List of routing decisions
        """
        decisions = []
        for claim in claims:
            decision = await self.route_claim(claim)
            decisions.append(decision)

        logger.info(
            "claims_routed",
            total=len(claims),
            domains={d.domain for d in decisions},
        )

        return decisions

    async def extract_claims(self, text: str, source: str = "") -> list[Claim]:
        """
        Extract verifiable claims from text.

        Args:
            text: Text to analyze
            source: Source of the text

        Returns:
            List of extracted claims
        """
        claims = []

        # Pattern-based claim extraction
        patterns = [
            # Results patterns
            (r"(?:we|our|the)\s+(?:show|demonstrate|prove|find|observe)\s+that\s+([^.]+\.)", "result_claim"),
            # Comparison patterns
            (r"(?:outperforms?|exceeds?|better\s+than)\s+([^.]+\.)", "comparison_claim"),
            # Performance patterns
            (r"(?:achieves?|obtains?|reaches?)\s+(?:an?\s+)?(?:accuracy|performance|score)\s+of\s+([^.]+\.)", "performance_claim"),
            # Statistical patterns
            (r"(?:p\s*[<=]\s*[\d.]+|statistically\s+significant|confidence\s+interval)\s*([^.]+\.)", "statistical_claim"),
            # Novel patterns
            (r"(?:novel|new|first|unique)\s+([^.]+\.)", "novelty_claim"),
        ]

        for pattern, claim_type in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                content = match.strip()
                if len(content) > 20:  # Minimum length for meaningful claim
                    claims.append(Claim(
                        claim_type=claim_type,
                        content=content,
                        source=source,
                        confidence=0.8,
                    ))

        # Deduplicate similar claims
        unique_claims = self._deduplicate_claims(claims)

        logger.info(
            "claims_extracted",
            total_found=len(claims),
            unique=len(unique_claims),
            source=source,
        )

        return unique_claims

    def _deduplicate_claims(self, claims: list[Claim]) -> list[Claim]:
        """Remove duplicate or very similar claims."""
        unique = []
        seen_content = set()

        for claim in claims:
            # Normalize content for comparison
            normalized = re.sub(r"\s+", " ", claim.content.lower().strip())

            # Check for similar content
            is_duplicate = False
            for seen in seen_content:
                if self._similarity(normalized, seen) > 0.8:
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique.append(claim)
                seen_content.add(normalized)

        return unique

    def _similarity(self, s1: str, s2: str) -> float:
        """Calculate simple similarity between strings."""
        words1 = set(s1.split())
        words2 = set(s2.split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def get_domain_info(self, domain: str) -> dict[str, Any]:
        """Get information about a research domain."""
        if domain not in RESEARCH_DOMAINS:
            return {"error": f"Unknown domain: {domain}"}

        config = RESEARCH_DOMAINS[domain]
        return {
            "domain": domain,
            "name": config["name"],
            "verification_engine": config["verification_engine"],
            "celery_queue": config["celery_queue"],
            "keywords": config["keywords"],
            "file_extensions": config["file_extensions"],
        }

    def get_all_domains(self) -> list[dict[str, Any]]:
        """Get information about all research domains."""
        return [
            {
                "domain": domain,
                "name": config["name"],
                "verification_engine": config["verification_engine"],
            }
            for domain, config in RESEARCH_DOMAINS.items()
        ]


# Singleton instance
_router_instance: ClaimRouter | None = None


def get_claim_router() -> ClaimRouter:
    """Get singleton ClaimRouter instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = ClaimRouter()
    return _router_instance

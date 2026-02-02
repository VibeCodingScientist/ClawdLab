"""Hypothesis generation and management for experiments."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from platform.experiments.base import Hypothesis, HypothesisStatus
from platform.experiments.config import HYPOTHESIS_TYPES, get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class HypothesisCandidate:
    """A candidate hypothesis before validation."""

    statement: str
    hypothesis_type: str
    confidence: float
    source: str
    variables: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    reasoning: str = ""


@dataclass
class HypothesisValidation:
    """Result of hypothesis validation."""

    is_valid: bool
    score: float
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    novelty_score: float = 0.0
    testability_score: float = 0.0
    clarity_score: float = 0.0


class HypothesisGenerator:
    """
    Generator for scientific hypotheses.

    Generates, validates, and prioritizes research hypotheses
    based on literature, existing knowledge, and domain patterns.
    """

    def __init__(self, mcp_tool_provider: Any | None = None):
        """
        Initialize hypothesis generator.

        Args:
            mcp_tool_provider: Optional MCP tool provider for LLM-based generation
        """
        self._mcp_provider = mcp_tool_provider
        self._hypotheses: dict[str, Hypothesis] = {}
        self._templates = HYPOTHESIS_TYPES

    async def generate_from_literature(
        self,
        paper_summaries: list[dict[str, Any]],
        domain: str,
        focus_area: str = "",
        max_hypotheses: int = 5,
    ) -> list[Hypothesis]:
        """
        Generate hypotheses from literature analysis.

        Args:
            paper_summaries: Summaries of relevant papers
            domain: Research domain
            focus_area: Specific area to focus on
            max_hypotheses: Maximum hypotheses to generate

        Returns:
            List of generated hypotheses
        """
        candidates = await self._extract_hypothesis_candidates(
            paper_summaries, domain, focus_area
        )

        # Validate and filter
        validated = []
        for candidate in candidates:
            validation = await self.validate_hypothesis(candidate)
            if validation.is_valid and validation.score >= settings.hypothesis_confidence_threshold:
                validated.append((candidate, validation))

        # Sort by score and take top
        validated.sort(key=lambda x: x[1].score, reverse=True)
        top_candidates = validated[:max_hypotheses]

        # Convert to Hypothesis objects
        hypotheses = []
        for candidate, validation in top_candidates:
            hypothesis = Hypothesis(
                title=self._generate_title(candidate.statement),
                statement=candidate.statement,
                hypothesis_type=candidate.hypothesis_type,
                variables=candidate.variables,
                source="literature",
                confidence=validation.score,
                related_papers=candidate.evidence,
                metadata={
                    "novelty_score": validation.novelty_score,
                    "testability_score": validation.testability_score,
                    "reasoning": candidate.reasoning,
                },
            )
            hypotheses.append(hypothesis)
            self._hypotheses[hypothesis.hypothesis_id] = hypothesis

        logger.info(
            "hypotheses_generated_from_literature",
            count=len(hypotheses),
            domain=domain,
        )

        return hypotheses

    async def generate_from_gap(
        self,
        existing_findings: list[str],
        domain: str,
        gap_description: str,
    ) -> list[Hypothesis]:
        """
        Generate hypotheses to fill a research gap.

        Args:
            existing_findings: Known findings in the area
            domain: Research domain
            gap_description: Description of the gap

        Returns:
            List of generated hypotheses
        """
        # Analyze the gap
        gap_analysis = await self._analyze_research_gap(
            existing_findings, gap_description
        )

        hypotheses = []

        # Generate hypotheses for each identified opportunity
        for opportunity in gap_analysis.get("opportunities", []):
            candidate = HypothesisCandidate(
                statement=opportunity["statement"],
                hypothesis_type=opportunity.get("type", "causal"),
                confidence=opportunity.get("confidence", 0.5),
                source="gap_analysis",
                variables=opportunity.get("variables", []),
                reasoning=opportunity.get("reasoning", ""),
            )

            validation = await self.validate_hypothesis(candidate)
            if validation.is_valid:
                hypothesis = Hypothesis(
                    title=self._generate_title(candidate.statement),
                    statement=candidate.statement,
                    hypothesis_type=candidate.hypothesis_type,
                    variables=candidate.variables,
                    source="gap_analysis",
                    confidence=validation.score,
                    metadata={
                        "gap_description": gap_description,
                        "reasoning": candidate.reasoning,
                    },
                )
                hypotheses.append(hypothesis)
                self._hypotheses[hypothesis.hypothesis_id] = hypothesis

        logger.info(
            "hypotheses_generated_from_gap",
            count=len(hypotheses),
            domain=domain,
        )

        return hypotheses

    async def generate_comparative(
        self,
        method_a: str,
        method_b: str,
        metrics: list[str],
        context: str = "",
    ) -> Hypothesis:
        """
        Generate a comparative hypothesis.

        Args:
            method_a: First method/approach
            method_b: Second method/approach
            metrics: Metrics to compare
            context: Additional context

        Returns:
            Comparative hypothesis
        """
        template = self._templates["comparative"]["template"]
        metric_str = ", ".join(metrics)

        statement = template.format(
            condition_a=method_a,
            condition_b=method_b,
            metric=metric_str,
        )

        hypothesis = Hypothesis(
            title=f"Comparison: {method_a} vs {method_b}",
            statement=statement,
            hypothesis_type="comparative",
            variables=[method_a, method_b] + metrics,
            predictions=[
                f"{method_a} will outperform {method_b} on {m}" for m in metrics
            ],
            source="user",
            confidence=0.5,
            metadata={"context": context},
        )

        self._hypotheses[hypothesis.hypothesis_id] = hypothesis

        return hypothesis

    async def generate_causal(
        self,
        condition: str,
        outcome: str,
        mechanism: str = "",
    ) -> Hypothesis:
        """
        Generate a causal hypothesis.

        Args:
            condition: The condition/intervention
            outcome: Expected outcome
            mechanism: Proposed mechanism

        Returns:
            Causal hypothesis
        """
        template = self._templates["causal"]["template"]

        statement = template.format(
            condition=condition,
            outcome=outcome,
            mechanism=mechanism or "an underlying mechanism",
        )

        hypothesis = Hypothesis(
            title=f"Effect of {condition} on {outcome}",
            statement=statement,
            hypothesis_type="causal",
            variables=[condition, outcome],
            predictions=[f"Increasing {condition} will increase {outcome}"],
            assumptions=[f"The mechanism ({mechanism}) is the primary pathway"],
            source="user",
            confidence=0.5,
        )

        self._hypotheses[hypothesis.hypothesis_id] = hypothesis

        return hypothesis

    async def validate_hypothesis(
        self,
        candidate: HypothesisCandidate | Hypothesis,
    ) -> HypothesisValidation:
        """
        Validate a hypothesis candidate.

        Args:
            candidate: Hypothesis to validate

        Returns:
            Validation result
        """
        issues = []
        suggestions = []

        # Get statement
        if isinstance(candidate, Hypothesis):
            statement = candidate.statement
            variables = candidate.variables
        else:
            statement = candidate.statement
            variables = candidate.variables

        # Check clarity
        clarity_score = self._assess_clarity(statement)
        if clarity_score < 0.5:
            issues.append("Hypothesis statement is unclear or ambiguous")
            suggestions.append("Make the hypothesis more specific and measurable")

        # Check testability
        testability_score = self._assess_testability(statement, variables)
        if testability_score < 0.5:
            issues.append("Hypothesis may not be easily testable")
            suggestions.append("Ensure variables can be measured or manipulated")

        # Check novelty (placeholder - would use knowledge base)
        novelty_score = await self._assess_novelty(statement)
        if novelty_score < 0.3:
            issues.append("Hypothesis may not be novel")
            suggestions.append("Consider a more specific or unique angle")

        # Calculate overall score
        overall_score = (clarity_score + testability_score + novelty_score) / 3

        is_valid = (
            len(issues) == 0
            or overall_score >= settings.hypothesis_confidence_threshold
        )

        return HypothesisValidation(
            is_valid=is_valid,
            score=overall_score,
            issues=issues,
            suggestions=suggestions,
            novelty_score=novelty_score,
            testability_score=testability_score,
            clarity_score=clarity_score,
        )

    async def prioritize_hypotheses(
        self,
        hypotheses: list[Hypothesis],
        criteria: dict[str, float] | None = None,
    ) -> list[Hypothesis]:
        """
        Prioritize hypotheses based on criteria.

        Args:
            hypotheses: Hypotheses to prioritize
            criteria: Weighting criteria (impact, feasibility, novelty)

        Returns:
            Sorted list of hypotheses
        """
        criteria = criteria or {
            "impact": 0.4,
            "feasibility": 0.3,
            "novelty": 0.3,
        }

        scored = []
        for hyp in hypotheses:
            # Calculate weighted score
            impact = self._estimate_impact(hyp)
            feasibility = self._estimate_feasibility(hyp)
            novelty = hyp.metadata.get("novelty_score", 0.5)

            score = (
                criteria.get("impact", 0) * impact
                + criteria.get("feasibility", 0) * feasibility
                + criteria.get("novelty", 0) * novelty
            )

            scored.append((hyp, score))

        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)

        # Update priorities
        for i, (hyp, score) in enumerate(scored):
            hyp.priority = i + 1
            hyp.confidence = score

        return [h for h, _ in scored]

    async def refine_hypothesis(
        self,
        hypothesis: Hypothesis,
        feedback: str,
    ) -> Hypothesis:
        """
        Refine a hypothesis based on feedback.

        Args:
            hypothesis: Hypothesis to refine
            feedback: Feedback for refinement

        Returns:
            Refined hypothesis
        """
        # Create refined version
        refined = Hypothesis(
            title=f"{hypothesis.title} (Refined)",
            statement=hypothesis.statement,  # Would be updated by LLM
            hypothesis_type=hypothesis.hypothesis_type,
            variables=hypothesis.variables,
            predictions=hypothesis.predictions,
            assumptions=hypothesis.assumptions,
            status=HypothesisStatus.REVISED,
            source=hypothesis.source,
            related_papers=hypothesis.related_papers,
            metadata={
                **hypothesis.metadata,
                "refined_from": hypothesis.hypothesis_id,
                "refinement_feedback": feedback,
            },
        )

        # If MCP provider available, use LLM to refine
        if self._mcp_provider:
            try:
                result = await self._mcp_provider.call_tool(
                    "refine_hypothesis",
                    {
                        "original": hypothesis.statement,
                        "feedback": feedback,
                    },
                )
                refined.statement = result.get("refined_statement", hypothesis.statement)
            except Exception as e:
                logger.warning("hypothesis_refinement_failed", error=str(e))

        self._hypotheses[refined.hypothesis_id] = refined

        return refined

    def get_hypothesis(self, hypothesis_id: str) -> Hypothesis | None:
        """Get hypothesis by ID."""
        return self._hypotheses.get(hypothesis_id)

    def list_hypotheses(
        self,
        status: HypothesisStatus | None = None,
        source: str | None = None,
    ) -> list[Hypothesis]:
        """List hypotheses with optional filtering."""
        hypotheses = list(self._hypotheses.values())

        if status:
            hypotheses = [h for h in hypotheses if h.status == status]

        if source:
            hypotheses = [h for h in hypotheses if h.source == source]

        return sorted(hypotheses, key=lambda h: h.priority)

    async def update_status(
        self,
        hypothesis_id: str,
        status: HypothesisStatus,
        evidence: list[str] | None = None,
    ) -> Hypothesis | None:
        """Update hypothesis status."""
        hypothesis = self._hypotheses.get(hypothesis_id)
        if not hypothesis:
            return None

        hypothesis.status = status
        hypothesis.updated_at = datetime.utcnow()

        if evidence:
            if status in (HypothesisStatus.SUPPORTED, HypothesisStatus.ACCEPTED):
                hypothesis.supporting_evidence.extend(evidence)
            elif status == HypothesisStatus.REFUTED:
                hypothesis.contradicting_evidence.extend(evidence)

        return hypothesis

    async def _extract_hypothesis_candidates(
        self,
        paper_summaries: list[dict[str, Any]],
        domain: str,
        focus_area: str,
    ) -> list[HypothesisCandidate]:
        """Extract hypothesis candidates from papers."""
        candidates = []

        # If MCP provider available, use LLM
        if self._mcp_provider:
            try:
                result = await self._mcp_provider.call_tool(
                    "extract_hypotheses",
                    {
                        "papers": paper_summaries,
                        "domain": domain,
                        "focus_area": focus_area,
                    },
                )

                for item in result.get("hypotheses", []):
                    candidates.append(
                        HypothesisCandidate(
                            statement=item.get("statement", ""),
                            hypothesis_type=item.get("type", "causal"),
                            confidence=item.get("confidence", 0.5),
                            source="literature",
                            variables=item.get("variables", []),
                            evidence=item.get("paper_ids", []),
                            reasoning=item.get("reasoning", ""),
                        )
                    )
            except Exception as e:
                logger.warning("hypothesis_extraction_failed", error=str(e))

        # Fallback: Simple pattern-based extraction
        if not candidates:
            candidates = self._simple_extraction(paper_summaries, domain)

        return candidates

    def _simple_extraction(
        self,
        paper_summaries: list[dict[str, Any]],
        domain: str,
    ) -> list[HypothesisCandidate]:
        """Simple pattern-based hypothesis extraction."""
        candidates = []

        # Look for claims and findings in abstracts
        claim_patterns = [
            "we show that",
            "we demonstrate",
            "our results suggest",
            "we find that",
            "this indicates",
        ]

        for paper in paper_summaries:
            abstract = paper.get("abstract", "").lower()

            for pattern in claim_patterns:
                if pattern in abstract:
                    # Extract sentence containing pattern
                    sentences = abstract.split(".")
                    for sent in sentences:
                        if pattern in sent:
                            candidates.append(
                                HypothesisCandidate(
                                    statement=sent.strip().capitalize() + ".",
                                    hypothesis_type="causal",
                                    confidence=0.4,
                                    source="literature",
                                    evidence=[paper.get("paper_id", "")],
                                )
                            )
                            break

        return candidates[:10]  # Limit to 10 candidates

    async def _analyze_research_gap(
        self,
        existing_findings: list[str],
        gap_description: str,
    ) -> dict[str, Any]:
        """Analyze research gap for opportunities."""
        # Placeholder - would use LLM or knowledge base
        return {
            "opportunities": [
                {
                    "statement": f"Addressing the gap: {gap_description}",
                    "type": "existence",
                    "confidence": 0.5,
                    "variables": [],
                    "reasoning": "Based on identified gap in existing research",
                }
            ]
        }

    def _generate_title(self, statement: str) -> str:
        """Generate a title from hypothesis statement."""
        # Take first 50 chars or up to first comma/period
        title = statement[:80]
        for sep in [",", ".", ";", ":"]:
            if sep in title:
                title = title.split(sep)[0]
                break
        return title.strip()

    def _assess_clarity(self, statement: str) -> float:
        """Assess clarity of hypothesis statement."""
        score = 1.0

        # Check length
        if len(statement) < 20:
            score -= 0.3
        if len(statement) > 500:
            score -= 0.2

        # Check for vague terms
        vague_terms = ["maybe", "might", "possibly", "somewhat", "kind of"]
        for term in vague_terms:
            if term in statement.lower():
                score -= 0.1

        # Check for quantifiable elements
        quantifiers = ["increase", "decrease", "more", "less", "higher", "lower"]
        if any(q in statement.lower() for q in quantifiers):
            score += 0.1

        return max(0.0, min(1.0, score))

    def _assess_testability(self, statement: str, variables: list[str]) -> float:
        """Assess testability of hypothesis."""
        score = 0.5

        # More variables = more testable
        if len(variables) >= 2:
            score += 0.2
        elif len(variables) == 1:
            score += 0.1

        # Check for measurable concepts
        measurable = ["performance", "accuracy", "rate", "level", "amount", "count"]
        if any(m in statement.lower() for m in measurable):
            score += 0.2

        # Check for comparison
        if "than" in statement.lower() or "compared to" in statement.lower():
            score += 0.1

        return max(0.0, min(1.0, score))

    async def _assess_novelty(self, statement: str) -> float:
        """Assess novelty of hypothesis."""
        # Placeholder - would check against knowledge base
        return 0.6

    def _estimate_impact(self, hypothesis: Hypothesis) -> float:
        """Estimate potential impact of hypothesis."""
        score = 0.5

        # Type-based impact
        type_impact = {
            "causal": 0.2,
            "existence": 0.15,
            "comparative": 0.1,
            "correlational": 0.05,
        }
        score += type_impact.get(hypothesis.hypothesis_type, 0)

        # Evidence-based impact
        if len(hypothesis.related_papers) > 5:
            score += 0.1

        return min(1.0, score)

    def _estimate_feasibility(self, hypothesis: Hypothesis) -> float:
        """Estimate feasibility of testing hypothesis."""
        score = 0.5

        # Variables affect feasibility
        if len(hypothesis.variables) <= 3:
            score += 0.2
        elif len(hypothesis.variables) > 5:
            score -= 0.1

        # Fewer assumptions = more feasible
        if len(hypothesis.assumptions) <= 2:
            score += 0.1
        elif len(hypothesis.assumptions) > 4:
            score -= 0.1

        return max(0.0, min(1.0, score))


# Singleton instance
_hypothesis_generator: HypothesisGenerator | None = None


def get_hypothesis_generator(
    mcp_tool_provider: Any | None = None,
) -> HypothesisGenerator:
    """Get singleton HypothesisGenerator instance."""
    global _hypothesis_generator
    if _hypothesis_generator is None:
        _hypothesis_generator = HypothesisGenerator(mcp_tool_provider)
    return _hypothesis_generator

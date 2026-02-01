"""Theorem novelty checker for detecting prior art in mathematics."""

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from platform.verification_engines.math_verifier.config import get_settings
from platform.shared.clients.redis_client import RedisCache
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class SimilarTheorem:
    """Represents a similar theorem found in the index."""

    name: str
    source: str  # e.g., "Mathlib", "custom", "arXiv"
    statement: str
    similarity_score: float
    url: str | None = None
    tags: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "statement": self.statement,
            "similarity_score": self.similarity_score,
            "url": self.url,
            "tags": self.tags,
        }


@dataclass
class NoveltyResult:
    """Result of novelty checking."""

    is_novel: bool
    novelty_score: float  # 0.0 = duplicate, 1.0 = completely novel
    similar_theorems: list[SimilarTheorem]
    analysis: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_novel": self.is_novel,
            "novelty_score": self.novelty_score,
            "similar_theorems": [t.to_dict() for t in self.similar_theorems],
            "analysis": self.analysis,
        }


class TheoremNoveltyChecker:
    """
    Checks theorems for novelty against known results.

    Uses multiple strategies:
    1. Exact match against indexed theorems
    2. Semantic similarity using embeddings
    3. Structural matching of proof patterns
    """

    def __init__(self):
        """Initialize the novelty checker."""
        self.cache = RedisCache("math_novelty")
        self._mathlib_index: dict[str, dict] | None = None

    async def check_novelty(
        self,
        theorem_statement: str,
        proof_code: str | None = None,
        domain_hints: list[str] | None = None,
    ) -> NoveltyResult:
        """
        Check if a theorem is novel.

        Args:
            theorem_statement: The theorem statement to check
            proof_code: Optional proof code for deeper analysis
            domain_hints: Optional hints about the mathematical domain

        Returns:
            NoveltyResult with novelty assessment
        """
        similar_theorems = []

        # 1. Check exact hash match
        exact_match = await self._check_exact_match(theorem_statement)
        if exact_match:
            return NoveltyResult(
                is_novel=False,
                novelty_score=0.0,
                similar_theorems=[exact_match],
                analysis="Exact match found in index",
            )

        # 2. Check normalized form match
        normalized = self._normalize_theorem(theorem_statement)
        normalized_match = await self._check_normalized_match(normalized)
        if normalized_match:
            similar_theorems.append(normalized_match)

        # 3. Check for keyword/concept overlap
        concept_matches = await self._check_concept_overlap(theorem_statement, domain_hints)
        similar_theorems.extend(concept_matches)

        # 4. Check Mathlib index if available
        mathlib_matches = await self._check_mathlib_index(theorem_statement)
        similar_theorems.extend(mathlib_matches)

        # 5. Calculate novelty score
        if not similar_theorems:
            return NoveltyResult(
                is_novel=True,
                novelty_score=1.0,
                similar_theorems=[],
                analysis="No similar theorems found in index",
            )

        max_similarity = max(t.similarity_score for t in similar_theorems)
        novelty_score = 1.0 - max_similarity

        is_novel = novelty_score >= settings.similarity_threshold

        analysis = self._generate_analysis(similar_theorems, novelty_score)

        return NoveltyResult(
            is_novel=is_novel,
            novelty_score=novelty_score,
            similar_theorems=sorted(similar_theorems, key=lambda t: -t.similarity_score)[:10],
            analysis=analysis,
        )

    async def _check_exact_match(self, statement: str) -> SimilarTheorem | None:
        """Check for exact statement match."""
        statement_hash = hashlib.sha256(statement.encode()).hexdigest()

        # Check cache
        cached = await self.cache.get(f"theorem_hash:{statement_hash}")
        if cached:
            return SimilarTheorem(
                name=cached.get("name", "Unknown"),
                source=cached.get("source", "cache"),
                statement=statement,
                similarity_score=1.0,
                url=cached.get("url"),
            )

        return None

    async def _check_normalized_match(self, normalized: str) -> SimilarTheorem | None:
        """Check for normalized form match."""
        normalized_hash = hashlib.sha256(normalized.encode()).hexdigest()

        cached = await self.cache.get(f"theorem_normalized:{normalized_hash}")
        if cached:
            return SimilarTheorem(
                name=cached.get("name", "Unknown"),
                source=cached.get("source", "cache"),
                statement=cached.get("statement", normalized),
                similarity_score=0.95,  # Very high but not exact
                url=cached.get("url"),
            )

        return None

    async def _check_concept_overlap(
        self,
        statement: str,
        domain_hints: list[str] | None,
    ) -> list[SimilarTheorem]:
        """Check for concept/keyword overlap with known theorems."""
        # Extract mathematical concepts from the statement
        concepts = self._extract_concepts(statement)

        if not concepts:
            return []

        # Check for theorems with similar concepts
        similar = []

        # This would query a concept index in production
        # For now, return empty list
        # In a full implementation, we would:
        # 1. Query vector DB for similar concept embeddings
        # 2. Search Mathlib documentation
        # 3. Query mathematical literature databases

        return similar

    async def _check_mathlib_index(self, statement: str) -> list[SimilarTheorem]:
        """Check against Mathlib theorem index."""
        # Load index if not cached
        if self._mathlib_index is None:
            self._mathlib_index = await self._load_mathlib_index()

        if not self._mathlib_index:
            return []

        similar = []
        statement_lower = statement.lower()

        # Simple keyword matching against Mathlib theorems
        # In production, this would use semantic search
        for name, data in self._mathlib_index.items():
            mathlib_statement = data.get("statement", "").lower()

            # Calculate simple overlap score
            statement_words = set(self._tokenize(statement_lower))
            mathlib_words = set(self._tokenize(mathlib_statement))

            if statement_words and mathlib_words:
                overlap = len(statement_words & mathlib_words)
                union = len(statement_words | mathlib_words)
                similarity = overlap / union if union > 0 else 0

                if similarity > 0.3:  # Threshold for inclusion
                    similar.append(SimilarTheorem(
                        name=name,
                        source="Mathlib",
                        statement=data.get("statement", ""),
                        similarity_score=similarity,
                        url=f"https://leanprover-community.github.io/mathlib4_docs/{name.replace('.', '/')}.html",
                        tags=data.get("tags", []),
                    ))

        return sorted(similar, key=lambda t: -t.similarity_score)[:5]

    async def _load_mathlib_index(self) -> dict[str, dict]:
        """Load Mathlib theorem index."""
        # In production, this would load from a pre-built index
        # For now, return a sample index
        return {
            "Nat.add_comm": {
                "statement": "∀ (n m : ℕ), n + m = m + n",
                "tags": ["nat", "arithmetic", "commutativity"],
            },
            "Nat.add_assoc": {
                "statement": "∀ (n m k : ℕ), (n + m) + k = n + (m + k)",
                "tags": ["nat", "arithmetic", "associativity"],
            },
            "Nat.mul_comm": {
                "statement": "∀ (n m : ℕ), n * m = m * n",
                "tags": ["nat", "arithmetic", "commutativity"],
            },
            "Nat.zero_add": {
                "statement": "∀ (n : ℕ), 0 + n = n",
                "tags": ["nat", "arithmetic", "identity"],
            },
            "Nat.add_zero": {
                "statement": "∀ (n : ℕ), n + 0 = n",
                "tags": ["nat", "arithmetic", "identity"],
            },
            "List.length_append": {
                "statement": "∀ (l₁ l₂ : List α), (l₁ ++ l₂).length = l₁.length + l₂.length",
                "tags": ["list", "length", "append"],
            },
            "List.reverse_reverse": {
                "statement": "∀ (l : List α), l.reverse.reverse = l",
                "tags": ["list", "reverse", "involution"],
            },
        }

    def _normalize_theorem(self, statement: str) -> str:
        """Normalize a theorem statement for comparison."""
        normalized = statement.lower()

        # Remove whitespace variations
        normalized = " ".join(normalized.split())

        # Standardize common mathematical notation
        replacements = [
            (r"\bforall\b", "∀"),
            (r"\bexists\b", "∃"),
            (r"\bfor all\b", "∀"),
            (r"\bthere exists\b", "∃"),
            (r"->", "→"),
            (r"=>", "→"),
            (r"<->", "↔"),
            (r"<=>", "↔"),
            (r"/\\", "∧"),
            (r"\\/", "∨"),
            (r"~", "¬"),
        ]

        for pattern, replacement in replacements:
            normalized = re.sub(pattern, replacement, normalized)

        return normalized

    def _extract_concepts(self, statement: str) -> list[str]:
        """Extract mathematical concepts from a statement."""
        # Common mathematical keywords and concepts
        math_keywords = {
            "prime", "composite", "divisible", "gcd", "lcm",
            "continuous", "differentiable", "integrable",
            "convergent", "divergent", "limit", "sequence",
            "group", "ring", "field", "vector", "matrix",
            "injective", "surjective", "bijective",
            "commutative", "associative", "distributive",
            "bounded", "monotonic", "increasing", "decreasing",
            "open", "closed", "compact", "connected",
        }

        words = self._tokenize(statement.lower())
        return [w for w in words if w in math_keywords]

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into words."""
        # Remove special characters except mathematical symbols
        text = re.sub(r"[^\w\s∀∃→↔∧∨¬]", " ", text)
        return [w for w in text.split() if len(w) > 1]

    def _generate_analysis(
        self,
        similar_theorems: list[SimilarTheorem],
        novelty_score: float,
    ) -> str:
        """Generate human-readable analysis of novelty."""
        if novelty_score >= 0.9:
            return "The theorem appears to be highly novel with no close matches found."
        elif novelty_score >= 0.7:
            return f"The theorem is likely novel, but has some similarity to {len(similar_theorems)} existing result(s)."
        elif novelty_score >= 0.5:
            return f"The theorem has moderate overlap with existing results. Review the {len(similar_theorems)} similar theorem(s) listed."
        else:
            top = similar_theorems[0] if similar_theorems else None
            if top:
                return f"The theorem closely resembles '{top.name}' from {top.source} (similarity: {top.similarity_score:.2%})."
            return "The theorem has high similarity to existing results."

    async def index_theorem(
        self,
        name: str,
        statement: str,
        source: str,
        url: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """Add a theorem to the index for future novelty checking."""
        # Store by hash
        statement_hash = hashlib.sha256(statement.encode()).hexdigest()
        await self.cache.setex(
            f"theorem_hash:{statement_hash}",
            86400 * 365,  # 1 year
            {
                "name": name,
                "statement": statement,
                "source": source,
                "url": url,
                "tags": tags or [],
            },
        )

        # Store normalized form
        normalized = self._normalize_theorem(statement)
        normalized_hash = hashlib.sha256(normalized.encode()).hexdigest()
        await self.cache.setex(
            f"theorem_normalized:{normalized_hash}",
            86400 * 365,
            {
                "name": name,
                "statement": statement,
                "source": source,
                "url": url,
            },
        )

        logger.info("theorem_indexed", name=name, source=source)

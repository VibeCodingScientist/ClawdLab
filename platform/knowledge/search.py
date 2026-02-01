"""Semantic search service for knowledge entries."""

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from platform.knowledge.base import (
    EntryType,
    KnowledgeEntry,
    SearchQuery,
    SearchResponse,
    SearchResult,
    VerificationStatus,
)
from platform.knowledge.config import get_settings
from platform.knowledge.repository import get_knowledge_repository
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""

    text: str
    embedding: list[float]
    model: str
    tokens_used: int = 0


class EmbeddingService:
    """Service for generating text embeddings."""

    def __init__(self, mcp_tool_provider: Any | None = None):
        """
        Initialize embedding service.

        Args:
            mcp_tool_provider: Optional MCP tool provider for embeddings
        """
        self._mcp_provider = mcp_tool_provider
        self._model = settings.embedding_model
        self._dimension = settings.vector_dimension
        self._cache: dict[str, list[float]] = {}

    async def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding for text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        # Check cache first
        cache_key = f"{self._model}:{hash(text)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        embedding = await self._generate_embedding_impl(text)

        # Cache result
        self._cache[cache_key] = embedding

        return embedding

    async def generate_embeddings_batch(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: Texts to embed

        Returns:
            List of embedding vectors
        """
        # Check cache and identify texts needing embedding
        results: list[list[float] | None] = [None] * len(texts)
        texts_to_embed: list[tuple[int, str]] = []

        for i, text in enumerate(texts):
            cache_key = f"{self._model}:{hash(text)}"
            if cache_key in self._cache:
                results[i] = self._cache[cache_key]
            else:
                texts_to_embed.append((i, text))

        # Generate embeddings for uncached texts
        if texts_to_embed:
            batch_size = settings.embedding_batch_size
            for batch_start in range(0, len(texts_to_embed), batch_size):
                batch = texts_to_embed[batch_start:batch_start + batch_size]
                batch_texts = [t[1] for t in batch]

                embeddings = await self._generate_embeddings_batch_impl(batch_texts)

                for j, (original_idx, text) in enumerate(batch):
                    embedding = embeddings[j]
                    results[original_idx] = embedding
                    # Cache result
                    cache_key = f"{self._model}:{hash(text)}"
                    self._cache[cache_key] = embedding

        return [r for r in results if r is not None]

    async def _generate_embedding_impl(self, text: str) -> list[float]:
        """Generate embedding using MCP or local fallback."""
        # Try MCP tool provider first
        if self._mcp_provider:
            try:
                result = await self._mcp_provider.call_tool(
                    "generate_embedding",
                    {
                        "text": text,
                        "model": self._model,
                    },
                )
                return result.get("embedding", [])
            except Exception as e:
                logger.warning("mcp_embedding_failed", error=str(e))

        # Fallback to local implementation (placeholder)
        return self._generate_local_embedding(text)

    async def _generate_embeddings_batch_impl(
        self,
        texts: list[str],
    ) -> list[list[float]]:
        """Generate embeddings for batch using MCP or local fallback."""
        # Try MCP tool provider first
        if self._mcp_provider:
            try:
                result = await self._mcp_provider.call_tool(
                    "generate_embeddings_batch",
                    {
                        "texts": texts,
                        "model": self._model,
                    },
                )
                return result.get("embeddings", [])
            except Exception as e:
                logger.warning("mcp_batch_embedding_failed", error=str(e))

        # Fallback to local implementation
        return [self._generate_local_embedding(t) for t in texts]

    def _generate_local_embedding(self, text: str) -> list[float]:
        """
        Generate local embedding placeholder.

        In production, this would use a local embedding model
        like sentence-transformers or similar.
        """
        # Generate deterministic pseudo-embedding based on text hash
        # This is a placeholder - real implementation would use actual model
        np.random.seed(hash(text) % (2**32))
        embedding = np.random.randn(self._dimension).astype(np.float32)
        # Normalize
        embedding = embedding / np.linalg.norm(embedding)
        return embedding.tolist()


class SemanticSearchService:
    """
    Semantic search service for knowledge entries.

    Provides vector-based similarity search with filtering and ranking.
    """

    def __init__(self, mcp_tool_provider: Any | None = None):
        """
        Initialize semantic search service.

        Args:
            mcp_tool_provider: Optional MCP tool provider
        """
        self._repository = get_knowledge_repository()
        self._embedding_service = EmbeddingService(mcp_tool_provider)
        self._mcp_provider = mcp_tool_provider

    async def search(self, query: SearchQuery) -> SearchResponse:
        """
        Search knowledge entries.

        Args:
            query: Search query

        Returns:
            Search response with results
        """
        start_time = time.time()

        # Generate query embedding if using semantic search
        query_embedding: list[float] | None = None
        if query.use_semantic and query.query:
            query_embedding = await self._embedding_service.generate_embedding(
                query.query
            )

        # Get all entries matching filters
        entries = await self._get_filtered_entries(query)

        # Score and rank entries
        scored_results = await self._score_entries(
            entries=entries,
            query=query,
            query_embedding=query_embedding,
        )

        # Apply limit and offset
        total_count = len(scored_results)
        paginated = scored_results[query.offset:query.offset + query.limit]

        # Build facets
        facets = self._build_facets(entries)

        query_time_ms = (time.time() - start_time) * 1000

        logger.info(
            "search_completed",
            query=query.query[:50] if query.query else "",
            total_results=total_count,
            returned=len(paginated),
            query_time_ms=round(query_time_ms, 2),
        )

        return SearchResponse(
            results=paginated,
            total_count=total_count,
            query_time_ms=query_time_ms,
            facets=facets,
        )

    async def find_similar(
        self,
        entry_id: str,
        limit: int = 10,
        min_similarity: float | None = None,
    ) -> list[SearchResult]:
        """
        Find entries similar to a given entry.

        Args:
            entry_id: Entry ID to find similar entries for
            limit: Maximum results
            min_similarity: Minimum similarity threshold

        Returns:
            List of similar entries
        """
        entry = await self._repository.get_entry(entry_id)
        if not entry:
            return []

        # Get or generate embedding for source entry
        if entry.embedding:
            source_embedding = entry.embedding
        else:
            # Generate embedding from content
            text = self._get_entry_text(entry)
            source_embedding = await self._embedding_service.generate_embedding(text)

            # Update entry with embedding
            await self._repository.update_entry(
                entry_id=entry_id,
                updates={"embedding": source_embedding},
            )

        # Get all other entries
        all_entries = await self._repository.list_entries(limit=10000)
        other_entries = [e for e in all_entries if e.entry_id != entry_id]

        # Score by similarity
        results = []
        threshold = min_similarity or settings.similarity_threshold

        for other in other_entries:
            if other.embedding:
                similarity = self._cosine_similarity(source_embedding, other.embedding)
            else:
                # Generate embedding for comparison
                other_text = self._get_entry_text(other)
                other_embedding = await self._embedding_service.generate_embedding(
                    other_text
                )
                similarity = self._cosine_similarity(source_embedding, other_embedding)

            if similarity >= threshold:
                results.append(
                    SearchResult(
                        entry=other,
                        score=similarity,
                        matched_fields=["embedding"],
                    )
                )

        # Sort by similarity and limit
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    async def index_entry(self, entry: KnowledgeEntry) -> KnowledgeEntry:
        """
        Index an entry for search by generating its embedding.

        Args:
            entry: Entry to index

        Returns:
            Entry with embedding
        """
        if not entry.embedding:
            text = self._get_entry_text(entry)
            entry.embedding = await self._embedding_service.generate_embedding(text)

            # Update in repository
            await self._repository.update_entry(
                entry_id=entry.entry_id,
                updates={"embedding": entry.embedding},
            )

        logger.info("entry_indexed", entry_id=entry.entry_id)
        return entry

    async def reindex_all(self) -> int:
        """
        Reindex all entries.

        Returns:
            Number of entries indexed
        """
        entries = await self._repository.list_entries(limit=100000)
        count = 0

        # Process in batches
        batch_size = settings.embedding_batch_size
        for i in range(0, len(entries), batch_size):
            batch = entries[i:i + batch_size]
            texts = [self._get_entry_text(e) for e in batch]

            embeddings = await self._embedding_service.generate_embeddings_batch(texts)

            for entry, embedding in zip(batch, embeddings):
                entry.embedding = embedding
                await self._repository.update_entry(
                    entry_id=entry.entry_id,
                    updates={"embedding": embedding},
                )
                count += 1

        logger.info("reindex_completed", count=count)
        return count

    async def _get_filtered_entries(
        self,
        query: SearchQuery,
    ) -> list[KnowledgeEntry]:
        """Get entries matching query filters."""
        # Start with all entries
        entries = await self._repository.list_entries(
            entry_type=query.entry_types[0] if len(query.entry_types) == 1 else None,
            domain=query.domains[0] if len(query.domains) == 1 else None,
            verification_status=(
                query.verification_statuses[0]
                if len(query.verification_statuses) == 1
                else None
            ),
            limit=10000,  # Get all for filtering
        )

        # Apply additional filters
        filtered = []
        for entry in entries:
            # Type filter
            if query.entry_types and entry.entry_type not in query.entry_types:
                continue

            # Domain filter
            if query.domains and entry.domain not in query.domains:
                continue

            # Status filter
            if (
                query.verification_statuses
                and entry.verification_status not in query.verification_statuses
            ):
                continue

            # Tag filter
            if query.tags and not any(tag in entry.tags for tag in query.tags):
                continue

            # Confidence filter
            if entry.confidence_score < query.min_confidence:
                continue

            # Date filters
            if query.date_from and entry.created_at < query.date_from:
                continue
            if query.date_to and entry.created_at > query.date_to:
                continue

            # Creator filter
            if query.created_by and entry.created_by != query.created_by:
                continue

            filtered.append(entry)

        return filtered

    async def _score_entries(
        self,
        entries: list[KnowledgeEntry],
        query: SearchQuery,
        query_embedding: list[float] | None,
    ) -> list[SearchResult]:
        """Score and rank entries."""
        results = []

        for entry in entries:
            score = 0.0
            matched_fields = []
            highlights = []

            # Semantic similarity score
            if query_embedding and query.use_semantic:
                if entry.embedding:
                    semantic_score = self._cosine_similarity(
                        query_embedding, entry.embedding
                    )
                else:
                    # Generate embedding on-the-fly
                    text = self._get_entry_text(entry)
                    entry_embedding = (
                        await self._embedding_service.generate_embedding(text)
                    )
                    semantic_score = self._cosine_similarity(
                        query_embedding, entry_embedding
                    )

                if semantic_score >= settings.similarity_threshold:
                    score += semantic_score * 0.6
                    matched_fields.append("semantic")

            # Keyword matching score
            if query.query:
                keyword_score, keyword_matches = self._keyword_score(entry, query.query)
                if keyword_score > 0:
                    score += keyword_score * 0.4
                    matched_fields.extend(keyword_matches)
                    highlights.extend(
                        self._extract_highlights(entry, query.query)
                    )

            # Boost verified entries
            if entry.verification_status == VerificationStatus.VERIFIED:
                score *= 1.2
            elif entry.verification_status == VerificationStatus.REFUTED:
                score *= 0.5

            # Boost by confidence
            score *= (0.5 + entry.confidence_score * 0.5)

            if score > 0 or not query.query:
                results.append(
                    SearchResult(
                        entry=entry,
                        score=score,
                        highlights=highlights[:3],  # Limit highlights
                        matched_fields=list(set(matched_fields)),
                    )
                )

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _keyword_score(
        self,
        entry: KnowledgeEntry,
        query: str,
    ) -> tuple[float, list[str]]:
        """Calculate keyword matching score."""
        query_terms = query.lower().split()
        score = 0.0
        matched_fields = []

        # Search in title (highest weight)
        title_lower = entry.title.lower()
        title_matches = sum(1 for term in query_terms if term in title_lower)
        if title_matches:
            score += title_matches * 0.4
            matched_fields.append("title")

        # Search in content
        content_lower = entry.content.lower()
        content_matches = sum(1 for term in query_terms if term in content_lower)
        if content_matches:
            score += content_matches * 0.3
            matched_fields.append("content")

        # Search in domain
        if any(term in entry.domain.lower() for term in query_terms):
            score += 0.2
            matched_fields.append("domain")

        # Search in tags
        tags_text = " ".join(entry.tags).lower()
        if any(term in tags_text for term in query_terms):
            score += 0.1
            matched_fields.append("tags")

        # Normalize by number of query terms
        if query_terms:
            score /= len(query_terms)

        return score, matched_fields

    def _extract_highlights(
        self,
        entry: KnowledgeEntry,
        query: str,
        context_chars: int = 100,
    ) -> list[str]:
        """Extract text highlights containing query terms."""
        highlights = []
        query_terms = query.lower().split()

        # Search in content
        content = entry.content
        content_lower = content.lower()

        for term in query_terms:
            idx = content_lower.find(term)
            if idx >= 0:
                start = max(0, idx - context_chars // 2)
                end = min(len(content), idx + len(term) + context_chars // 2)
                highlight = content[start:end]
                if start > 0:
                    highlight = "..." + highlight
                if end < len(content):
                    highlight = highlight + "..."
                highlights.append(highlight)

        return highlights

    def _build_facets(
        self,
        entries: list[KnowledgeEntry],
    ) -> dict[str, dict[str, int]]:
        """Build facet counts from entries."""
        facets: dict[str, dict[str, int]] = {
            "entry_type": {},
            "domain": {},
            "verification_status": {},
        }

        for entry in entries:
            # Entry type facet
            type_val = entry.entry_type.value
            facets["entry_type"][type_val] = facets["entry_type"].get(type_val, 0) + 1

            # Domain facet
            facets["domain"][entry.domain] = facets["domain"].get(entry.domain, 0) + 1

            # Status facet
            status_val = entry.verification_status.value
            facets["verification_status"][status_val] = (
                facets["verification_status"].get(status_val, 0) + 1
            )

        return facets

    def _get_entry_text(self, entry: KnowledgeEntry) -> str:
        """Get searchable text from entry."""
        parts = [entry.title, entry.content, entry.domain]
        parts.extend(entry.tags)
        return " ".join(parts)

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        a_arr = np.array(a)
        b_arr = np.array(b)

        dot_product = np.dot(a_arr, b_arr)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(dot_product / (norm_a * norm_b))


# Singleton instance
_search_service_instance: SemanticSearchService | None = None


def get_search_service(
    mcp_tool_provider: Any | None = None,
) -> SemanticSearchService:
    """Get singleton SemanticSearchService instance."""
    global _search_service_instance
    if _search_service_instance is None:
        _search_service_instance = SemanticSearchService(mcp_tool_provider)
    return _search_service_instance

"""ML novelty checker with Papers With Code integration."""

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp

from platform.verification_engines.ml_verifier.config import get_settings
from platform.shared.clients.redis_client import RedisCache
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@dataclass
class SimilarPaper:
    """Represents a similar paper from the index."""

    title: str
    authors: list[str]
    paper_url: str
    code_url: str | None
    arxiv_id: str | None
    published_date: str | None
    similarity_score: float
    metrics: dict[str, float] | None = None
    tasks: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "authors": self.authors,
            "paper_url": self.paper_url,
            "code_url": self.code_url,
            "arxiv_id": self.arxiv_id,
            "published_date": self.published_date,
            "similarity_score": self.similarity_score,
            "metrics": self.metrics,
            "tasks": self.tasks,
        }


@dataclass
class MLNoveltyResult:
    """Result of ML novelty checking."""

    is_novel: bool
    novelty_score: float  # 0.0 = duplicate, 1.0 = completely novel
    similar_papers: list[SimilarPaper]
    sota_comparison: dict[str, Any] | None
    analysis: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_novel": self.is_novel,
            "novelty_score": self.novelty_score,
            "similar_papers": [p.to_dict() for p in self.similar_papers],
            "sota_comparison": self.sota_comparison,
            "analysis": self.analysis,
        }


class MLNoveltyChecker:
    """
    Checks ML experiments for novelty against existing research.

    Integrates with:
    - Papers With Code for benchmarks and SOTA
    - Semantic Scholar for paper similarity
    - arXiv for preprints
    """

    PAPERS_WITH_CODE_API = "https://paperswithcode.com/api/v1"
    SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1"

    def __init__(self):
        """Initialize novelty checker."""
        self.cache = RedisCache("ml_novelty")

    async def check_novelty(
        self,
        experiment_description: str,
        tasks: list[str],
        metrics: dict[str, float],
        dataset_names: list[str] | None = None,
        model_architecture: str | None = None,
    ) -> MLNoveltyResult:
        """
        Check if an ML experiment result is novel.

        Args:
            experiment_description: Description of the experiment
            tasks: ML tasks (e.g., "image-classification", "question-answering")
            metrics: Achieved metrics
            dataset_names: Datasets used
            model_architecture: Model architecture name

        Returns:
            MLNoveltyResult with novelty assessment
        """
        similar_papers = []

        # 1. Check Papers With Code for similar benchmarks
        if settings.papers_with_code_enabled:
            pwc_results = await self._search_papers_with_code(
                tasks=tasks,
                datasets=dataset_names or [],
            )
            similar_papers.extend(pwc_results)

        # 2. Check for SOTA on specified benchmarks
        sota_comparison = await self._compare_to_sota(
            tasks=tasks,
            metrics=metrics,
            datasets=dataset_names or [],
        )

        # 3. Search Semantic Scholar for similar work
        if settings.semantic_scholar_api_key:
            semantic_results = await self._search_semantic_scholar(
                query=experiment_description,
                model_architecture=model_architecture,
            )
            similar_papers.extend(semantic_results)

        # 4. Calculate novelty score
        novelty_score = self._calculate_novelty_score(
            similar_papers=similar_papers,
            sota_comparison=sota_comparison,
            metrics=metrics,
        )

        is_novel = novelty_score >= 0.3  # Threshold for novelty

        analysis = self._generate_analysis(
            similar_papers=similar_papers,
            sota_comparison=sota_comparison,
            novelty_score=novelty_score,
        )

        return MLNoveltyResult(
            is_novel=is_novel,
            novelty_score=novelty_score,
            similar_papers=sorted(similar_papers, key=lambda p: -p.similarity_score)[:10],
            sota_comparison=sota_comparison,
            analysis=analysis,
        )

    async def _search_papers_with_code(
        self,
        tasks: list[str],
        datasets: list[str],
    ) -> list[SimilarPaper]:
        """Search Papers With Code for similar work."""
        similar = []

        async with aiohttp.ClientSession() as session:
            # Search by task
            for task in tasks:
                task_slug = task.lower().replace(" ", "-")

                try:
                    url = f"{self.PAPERS_WITH_CODE_API}/tasks/{task_slug}/papers/"
                    async with session.get(url, timeout=30) as response:
                        if response.status == 200:
                            data = await response.json()

                            for paper_data in data.get("results", [])[:5]:
                                similar.append(SimilarPaper(
                                    title=paper_data.get("title", ""),
                                    authors=paper_data.get("authors", []),
                                    paper_url=paper_data.get("url_abs", ""),
                                    code_url=paper_data.get("url_code"),
                                    arxiv_id=paper_data.get("arxiv_id"),
                                    published_date=paper_data.get("published"),
                                    similarity_score=0.5,  # Base similarity for same task
                                    tasks=[task],
                                ))

                except Exception as e:
                    logger.warning("pwc_search_error", task=task, error=str(e))

            # Search by dataset
            for dataset in datasets:
                dataset_slug = dataset.lower().replace(" ", "-")

                try:
                    url = f"{self.PAPERS_WITH_CODE_API}/datasets/{dataset_slug}/papers/"
                    async with session.get(url, timeout=30) as response:
                        if response.status == 200:
                            data = await response.json()

                            for paper_data in data.get("results", [])[:3]:
                                similar.append(SimilarPaper(
                                    title=paper_data.get("title", ""),
                                    authors=paper_data.get("authors", []),
                                    paper_url=paper_data.get("url_abs", ""),
                                    code_url=paper_data.get("url_code"),
                                    arxiv_id=paper_data.get("arxiv_id"),
                                    published_date=paper_data.get("published"),
                                    similarity_score=0.4,
                                ))

                except Exception as e:
                    logger.warning("pwc_dataset_search_error", dataset=dataset, error=str(e))

        return similar

    async def _compare_to_sota(
        self,
        tasks: list[str],
        metrics: dict[str, float],
        datasets: list[str],
    ) -> dict[str, Any]:
        """Compare metrics to state-of-the-art results."""
        sota_data = {}

        async with aiohttp.ClientSession() as session:
            for task in tasks:
                task_slug = task.lower().replace(" ", "-")

                for dataset in datasets:
                    dataset_slug = dataset.lower().replace(" ", "-")

                    try:
                        url = f"{self.PAPERS_WITH_CODE_API}/sota/{task_slug}/{dataset_slug}/"
                        async with session.get(url, timeout=30) as response:
                            if response.status == 200:
                                data = await response.json()

                                sota_entries = data.get("rows", [])
                                if sota_entries:
                                    best = sota_entries[0]
                                    sota_key = f"{task}/{dataset}"
                                    sota_data[sota_key] = {
                                        "sota_paper": best.get("model_name", ""),
                                        "sota_metrics": best.get("metrics", {}),
                                        "rank": self._calculate_rank(
                                            our_metrics=metrics,
                                            leaderboard=sota_entries,
                                        ),
                                    }

                    except Exception as e:
                        logger.warning("sota_fetch_error", task=task, dataset=dataset, error=str(e))

        return sota_data if sota_data else None

    def _calculate_rank(
        self,
        our_metrics: dict[str, float],
        leaderboard: list[dict[str, Any]],
    ) -> int | None:
        """Calculate where our metrics would rank on the leaderboard."""
        if not leaderboard:
            return None

        # Find common metric
        if not our_metrics:
            return None

        # Use first metric we have
        metric_name = list(our_metrics.keys())[0]
        our_value = our_metrics[metric_name]

        # Count how many entries we beat
        rank = 1
        for entry in leaderboard:
            entry_metrics = entry.get("metrics", {})
            entry_value = entry_metrics.get(metric_name)
            if entry_value is not None and entry_value > our_value:
                rank += 1

        return rank

    async def _search_semantic_scholar(
        self,
        query: str,
        model_architecture: str | None = None,
    ) -> list[SimilarPaper]:
        """Search Semantic Scholar for similar papers."""
        similar = []

        search_query = query
        if model_architecture:
            search_query = f"{model_architecture} {query}"

        async with aiohttp.ClientSession() as session:
            try:
                headers = {}
                if settings.semantic_scholar_api_key:
                    headers["x-api-key"] = settings.semantic_scholar_api_key

                url = f"{self.SEMANTIC_SCHOLAR_API}/paper/search"
                params = {
                    "query": search_query[:200],  # Limit query length
                    "limit": 10,
                    "fields": "title,authors,url,externalIds,publicationDate,citationCount",
                }

                async with session.get(url, params=params, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()

                        for paper_data in data.get("data", []):
                            authors = [
                                a.get("name", "")
                                for a in paper_data.get("authors", [])
                            ]

                            external_ids = paper_data.get("externalIds", {})
                            arxiv_id = external_ids.get("ArXiv")

                            citation_count = paper_data.get("citationCount", 0)
                            # Higher citations = higher similarity (more influential)
                            sim_score = min(0.3 + (citation_count / 1000), 0.7)

                            similar.append(SimilarPaper(
                                title=paper_data.get("title", ""),
                                authors=authors,
                                paper_url=paper_data.get("url", ""),
                                code_url=None,
                                arxiv_id=arxiv_id,
                                published_date=paper_data.get("publicationDate"),
                                similarity_score=sim_score,
                            ))

            except Exception as e:
                logger.warning("semantic_scholar_error", error=str(e))

        return similar

    def _calculate_novelty_score(
        self,
        similar_papers: list[SimilarPaper],
        sota_comparison: dict[str, Any] | None,
        metrics: dict[str, float],
    ) -> float:
        """Calculate overall novelty score."""
        # Start with base score
        score = 0.7

        # Reduce score based on similar papers
        if similar_papers:
            max_similarity = max(p.similarity_score for p in similar_papers)
            score -= max_similarity * 0.3

        # Adjust based on SOTA comparison
        if sota_comparison:
            for task_data in sota_comparison.values():
                rank = task_data.get("rank")
                if rank:
                    if rank == 1:
                        score += 0.3  # New SOTA is very novel
                    elif rank <= 3:
                        score += 0.1  # Near SOTA is somewhat novel
                    elif rank > 10:
                        score -= 0.1  # Far from SOTA reduces novelty

        # Clamp to [0, 1]
        return max(0.0, min(1.0, score))

    def _generate_analysis(
        self,
        similar_papers: list[SimilarPaper],
        sota_comparison: dict[str, Any] | None,
        novelty_score: float,
    ) -> str:
        """Generate human-readable analysis."""
        parts = []

        # Novelty assessment
        if novelty_score >= 0.7:
            parts.append("The results appear to be highly novel.")
        elif novelty_score >= 0.5:
            parts.append("The results show moderate novelty.")
        elif novelty_score >= 0.3:
            parts.append("The results have limited novelty compared to existing work.")
        else:
            parts.append("The results closely resemble existing published work.")

        # Similar papers
        if similar_papers:
            top_papers = similar_papers[:3]
            titles = ", ".join([f'"{p.title}"' for p in top_papers])
            parts.append(f"Similar work includes: {titles}.")

        # SOTA comparison
        if sota_comparison:
            for task_key, data in sota_comparison.items():
                rank = data.get("rank")
                if rank:
                    if rank == 1:
                        parts.append(f"Results achieve new state-of-the-art on {task_key}.")
                    else:
                        parts.append(f"Results rank #{rank} on {task_key} leaderboard.")

        return " ".join(parts)

    async def index_experiment(
        self,
        experiment_id: str,
        description: str,
        tasks: list[str],
        metrics: dict[str, float],
        paper_url: str | None = None,
        code_url: str | None = None,
    ) -> None:
        """
        Index an experiment for future novelty checking.

        Args:
            experiment_id: Unique experiment identifier
            description: Experiment description
            tasks: ML tasks
            metrics: Achieved metrics
            paper_url: Optional paper URL
            code_url: Optional code URL
        """
        # Create hash of experiment
        hash_input = f"{description}:{','.join(tasks)}:{json.dumps(metrics, sort_keys=True)}"
        exp_hash = hashlib.sha256(hash_input.encode()).hexdigest()

        import json
        await self.cache.setex(
            f"ml_experiment:{exp_hash}",
            86400 * 365,  # 1 year
            {
                "experiment_id": experiment_id,
                "description": description,
                "tasks": tasks,
                "metrics": metrics,
                "paper_url": paper_url,
                "code_url": code_url,
                "indexed_at": datetime.utcnow().isoformat(),
            },
        )

        logger.info("ml_experiment_indexed", experiment_id=experiment_id)

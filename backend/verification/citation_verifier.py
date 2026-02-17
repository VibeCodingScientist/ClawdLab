"""Cross-cutting verifier: Citation & Reference Verification.

Validates citations in task results by checking DOI resolution,
metadata matching via OpenAlex + Semantic Scholar, claim-text
support via abstract similarity, and reference freshness.
"""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any

import httpx

from backend.logging_config import get_logger
from backend.verification.cross_cutting_base import (
    CrossCuttingResult,
    CrossCuttingVerifier,
)

logger = get_logger(__name__)

CROSSREF_API = "https://api.crossref.org/works"
OPENALEX_API = "https://api.openalex.org/works"
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper"

MAX_CITATIONS = 10
HTTP_TIMEOUT = 30

# Fields in fast-moving domains get freshness penalties
FAST_MOVING_DOMAINS = {"ml_ai", "bioinformatics", "computational_biology"}
FRESHNESS_THRESHOLD_FAST = 5   # years
FRESHNESS_THRESHOLD_SLOW = 15  # years


class CitationVerifier(CrossCuttingVerifier):
    name = "citation_reference"
    default_weight = 0.15

    def is_applicable(self, task_result: dict, task_metadata: dict) -> bool:
        citation_keys = {"citations", "references", "papers", "bibliography"}
        return any(
            k in task_result and task_result[k]
            for k in citation_keys
        )

    async def verify(self, task_result: dict, task_metadata: dict) -> CrossCuttingResult:
        start = time.monotonic()
        domain = task_metadata.get("domain", "general")

        citations = self._extract_citations(task_result)
        if not citations:
            return CrossCuttingResult(
                verifier_name=self.name,
                score=0.0,
                weight=self.default_weight,
                errors=["No parseable citations found"],
                compute_time_seconds=time.monotonic() - start,
            )

        # Cap at MAX_CITATIONS
        citations = citations[:MAX_CITATIONS]

        # Run all citation checks concurrently
        results = await asyncio.gather(
            *[self._check_citation(c, domain) for c in citations],
            return_exceptions=True,
        )

        citation_details: list[dict] = []
        total_score = 0.0
        valid_count = 0

        for i, r in enumerate(results):
            if isinstance(r, Exception):
                citation_details.append({
                    "citation": citations[i].get("title", f"citation_{i}"),
                    "error": str(r),
                    "score": 0.0,
                })
            else:
                citation_details.append(r)
                total_score += r.get("score", 0.0)
                valid_count += 1

        avg_score = total_score / len(citations) if citations else 0.0
        elapsed = time.monotonic() - start

        return CrossCuttingResult(
            verifier_name=self.name,
            score=round(avg_score, 4),
            weight=self.default_weight,
            details={
                "citations_checked": len(citations),
                "citations_valid": valid_count,
                "citation_results": citation_details,
            },
            compute_time_seconds=elapsed,
        )

    def _extract_citations(self, task_result: dict) -> list[dict]:
        """Extract citation objects from various possible keys/formats."""
        for key in ("citations", "references", "papers", "bibliography"):
            raw = task_result.get(key)
            if not raw:
                continue
            if isinstance(raw, list):
                return [self._normalize_citation(c) for c in raw if c]
        return []

    @staticmethod
    def _normalize_citation(citation: Any) -> dict:
        """Normalise a citation to {title, doi, authors, year, claim_text}."""
        if isinstance(citation, str):
            return {"title": citation}
        if isinstance(citation, dict):
            return {
                "title": citation.get("title", ""),
                "doi": citation.get("doi", ""),
                "authors": citation.get("authors", []),
                "year": citation.get("year"),
                "claim_text": citation.get("claim_text", citation.get("relevance", "")),
                "url": citation.get("url", ""),
                "abstract": citation.get("abstract", ""),
            }
        return {"title": str(citation)}

    async def _check_citation(self, citation: dict, domain: str) -> dict:
        """Run all 4 component checks on a single citation."""
        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {"title": citation.get("title", "")}

        doi = citation.get("doi", "")
        if not doi:
            doi = self._extract_doi_from_url(citation.get("url", ""))

        # Component 1: DOI resolution (0.30)
        if doi:
            doi_result = await self._resolve_doi(doi)
            component_scores["doi_resolution"] = doi_result["score"]
            details["doi"] = doi_result
        else:
            component_scores["doi_resolution"] = 0.0
            details["doi"] = {"note": "No DOI provided"}

        # Component 2: Metadata match (0.30)
        meta_result = await self._check_metadata_match(citation)
        component_scores["metadata_match"] = meta_result["score"]
        details["metadata"] = meta_result

        # Component 3: Claim support (0.25)
        claim_score = self._check_claim_support(citation, meta_result.get("abstract", ""))
        component_scores["claim_support"] = claim_score
        details["claim_support_score"] = claim_score

        # Component 4: Freshness (0.15)
        freshness_score = self._check_freshness(citation, domain)
        component_scores["freshness"] = freshness_score
        details["freshness_score"] = freshness_score

        weights = {
            "doi_resolution": 0.30,
            "metadata_match": 0.30,
            "claim_support": 0.25,
            "freshness": 0.15,
        }

        score = sum(weights[k] * component_scores[k] for k in weights)
        details["component_scores"] = component_scores
        details["score"] = round(score, 4)

        return details

    @staticmethod
    def _extract_doi_from_url(url: str) -> str:
        """Try to extract a DOI from a URL."""
        match = re.search(r"10\.\d{4,}/[^\s]+", url)
        return match.group(0).rstrip(".,;)") if match else ""

    async def _resolve_doi(self, doi: str) -> dict:
        """Resolve DOI via CrossRef API; check for retraction notices."""
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(f"{CROSSREF_API}/{doi}")
                if resp.status_code == 200:
                    data = resp.json().get("message", {})

                    # Check for retraction / correction / withdrawal via
                    # CrossRef's "update-to" field (includes Retraction Watch data)
                    retraction_info = self._check_retraction_status(data)

                    score = 1.0
                    if retraction_info.get("retracted"):
                        score = 0.1  # severe penalty — paper is retracted
                    elif retraction_info.get("has_correction"):
                        score = 0.7  # mild penalty — paper has correction/erratum

                    result = {
                        "score": score,
                        "resolved": True,
                        "title": data.get("title", [""])[0] if data.get("title") else "",
                        "doi": doi,
                    }
                    if retraction_info.get("retracted") or retraction_info.get("has_correction"):
                        result["retraction_status"] = retraction_info
                    return result
                return {"score": 0.0, "resolved": False, "status": resp.status_code}
        except Exception as e:
            logger.warning("doi_resolution_failed", doi=doi, error=str(e))
            return {"score": 0.0, "resolved": False, "error": str(e)}

    @staticmethod
    def _check_retraction_status(crossref_data: dict) -> dict:
        """Inspect CrossRef metadata for retraction/correction notices."""
        update_to = crossref_data.get("update-to", [])
        if not update_to:
            return {"retracted": False, "has_correction": False}

        retracted = False
        has_correction = False
        notices: list[str] = []

        for update in update_to:
            update_type = (update.get("type", "") or "").lower()
            label = update.get("label", "") or update_type
            if any(kw in update_type for kw in ("retraction", "withdrawal")):
                retracted = True
                notices.append(label)
            elif any(kw in update_type for kw in ("correction", "erratum")):
                has_correction = True
                notices.append(label)

        return {
            "retracted": retracted,
            "has_correction": has_correction,
            "notices": notices,
        }

    async def _check_metadata_match(self, citation: dict) -> dict:
        """Check title/author/year match via OpenAlex and Semantic Scholar."""
        title = citation.get("title", "")
        if not title:
            return {"score": 0.0, "note": "No title to match"}

        # Try OpenAlex first
        oa_result = await self._query_openalex(title)
        if oa_result["score"] >= 0.7:
            return oa_result

        # Fallback to Semantic Scholar
        ss_result = await self._query_semantic_scholar(title)
        return max([oa_result, ss_result], key=lambda r: r["score"])

    async def _query_openalex(self, title: str) -> dict:
        """Query OpenAlex for title match."""
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(
                    OPENALEX_API,
                    params={"filter": f"title.search:{title[:200]}", "per_page": "1"},
                )
                if resp.status_code != 200:
                    return {"score": 0.0, "source": "openalex", "error": f"HTTP {resp.status_code}"}

                results = resp.json().get("results", [])
                if not results:
                    return {"score": 0.0, "source": "openalex", "note": "No results"}

                top = results[0]
                oa_title = top.get("title", "")
                similarity = _jaccard_similarity(title.lower(), oa_title.lower())

                return {
                    "score": round(min(1.0, similarity * 1.25), 4),
                    "source": "openalex",
                    "matched_title": oa_title,
                    "similarity": round(similarity, 4),
                    "abstract": top.get("abstract", "") or "",
                    "year": top.get("publication_year"),
                }
        except Exception as e:
            logger.warning("openalex_query_failed", error=str(e))
            return {"score": 0.0, "source": "openalex", "error": str(e)}

    async def _query_semantic_scholar(self, title: str) -> dict:
        """Query Semantic Scholar for title match."""
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                resp = await client.get(
                    f"{SEMANTIC_SCHOLAR_API}/search",
                    params={"query": title[:200], "limit": "1", "fields": "title,abstract,year,authors"},
                )
                if resp.status_code != 200:
                    return {"score": 0.0, "source": "semantic_scholar", "error": f"HTTP {resp.status_code}"}

                data = resp.json().get("data", [])
                if not data:
                    return {"score": 0.0, "source": "semantic_scholar", "note": "No results"}

                top = data[0]
                ss_title = top.get("title", "")
                similarity = _jaccard_similarity(title.lower(), ss_title.lower())

                return {
                    "score": round(min(1.0, similarity * 1.25), 4),
                    "source": "semantic_scholar",
                    "matched_title": ss_title,
                    "similarity": round(similarity, 4),
                    "abstract": top.get("abstract", "") or "",
                    "year": top.get("year"),
                }
        except Exception as e:
            logger.warning("semantic_scholar_query_failed", error=str(e))
            return {"score": 0.0, "source": "semantic_scholar", "error": str(e)}

    @staticmethod
    def _check_claim_support(citation: dict, fetched_abstract: str) -> float:
        """Check if claim text is supported by paper abstract."""
        claim_text = citation.get("claim_text", "")
        abstract = fetched_abstract or citation.get("abstract", "")

        if not claim_text or not abstract:
            return 0.5  # neutral — can't check

        similarity = _jaccard_similarity(claim_text.lower(), abstract.lower())
        return round(min(1.0, similarity * 2.0), 4)

    @staticmethod
    def _check_freshness(citation: dict, domain: str) -> float:
        """Penalize old references in fast-moving fields."""
        year = citation.get("year")
        if not year or not isinstance(year, (int, float)):
            return 0.5  # neutral

        import datetime
        current_year = datetime.datetime.now(datetime.timezone.utc).year
        age = current_year - int(year)

        if age < 0:
            return 0.8  # future year — slight penalty for plausibility

        threshold = (
            FRESHNESS_THRESHOLD_FAST
            if domain in FAST_MOVING_DOMAINS
            else FRESHNESS_THRESHOLD_SLOW
        )

        if age <= threshold:
            return 1.0
        elif age <= threshold * 2:
            return round(max(0.3, 1.0 - (age - threshold) / threshold), 4)
        return 0.3


def _jaccard_similarity(a: str, b: str) -> float:
    """Word-level Jaccard similarity between two strings."""
    words_a = set(a.split())
    words_b = set(b.split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0

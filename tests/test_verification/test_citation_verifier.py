"""Tests for citation & reference verifier."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.verification.citation_verifier import CitationVerifier, _jaccard_similarity


@pytest.fixture
def verifier():
    return CitationVerifier()


class TestApplicability:
    def test_applicable_with_citations(self, verifier):
        assert verifier.is_applicable({"citations": [{"title": "Test"}]}, {}) is True

    def test_applicable_with_references(self, verifier):
        assert verifier.is_applicable({"references": [{"title": "Test"}]}, {}) is True

    def test_applicable_with_papers(self, verifier):
        assert verifier.is_applicable({"papers": [{"title": "Test"}]}, {}) is True

    def test_applicable_with_bibliography(self, verifier):
        assert verifier.is_applicable({"bibliography": [{"title": "Test"}]}, {}) is True

    def test_not_applicable_empty(self, verifier):
        assert verifier.is_applicable({}, {}) is False

    def test_not_applicable_empty_list(self, verifier):
        assert verifier.is_applicable({"citations": []}, {}) is False


class TestJaccardSimilarity:
    def test_identical(self):
        assert _jaccard_similarity("hello world", "hello world") == 1.0

    def test_no_overlap(self):
        assert _jaccard_similarity("hello world", "foo bar") == 0.0

    def test_partial_overlap(self):
        sim = _jaccard_similarity("the quick brown fox", "the lazy brown dog")
        assert 0.0 < sim < 1.0

    def test_empty_strings(self):
        assert _jaccard_similarity("", "") == 0.0
        assert _jaccard_similarity("hello", "") == 0.0


class TestExtractCitations:
    def test_extract_from_list_of_dicts(self, verifier):
        result = {"citations": [{"title": "Paper A", "doi": "10.1234/test"}]}
        citations = verifier._extract_citations(result)
        assert len(citations) == 1
        assert citations[0]["title"] == "Paper A"

    def test_extract_from_list_of_strings(self, verifier):
        result = {"references": ["Paper A", "Paper B"]}
        citations = verifier._extract_citations(result)
        assert len(citations) == 2
        assert citations[0]["title"] == "Paper A"

    def test_extract_empty(self, verifier):
        assert verifier._extract_citations({}) == []
        assert verifier._extract_citations({"citations": []}) == []


class TestExtractDOI:
    def test_extract_from_url(self):
        doi = CitationVerifier._extract_doi_from_url("https://doi.org/10.1038/s41586-023-06474-x")
        assert doi == "10.1038/s41586-023-06474-x"

    def test_no_doi_in_url(self):
        doi = CitationVerifier._extract_doi_from_url("https://example.com/paper")
        assert doi == ""


class TestFreshness:
    def test_recent_paper_high_score(self):
        citation = {"year": 2025}
        score = CitationVerifier._check_freshness(citation, "ml_ai")
        assert score == 1.0

    def test_old_paper_fast_domain(self):
        citation = {"year": 2010}
        score = CitationVerifier._check_freshness(citation, "ml_ai")
        assert score < 1.0

    def test_old_paper_slow_domain(self):
        citation = {"year": 2015}
        score = CitationVerifier._check_freshness(citation, "mathematics")
        assert score == 1.0

    def test_no_year_neutral(self):
        score = CitationVerifier._check_freshness({}, "ml_ai")
        assert score == 0.5


class TestClaimSupport:
    def test_matching_text(self):
        citation = {"claim_text": "deep learning improves accuracy on benchmarks"}
        abstract = "deep learning methods improve accuracy on standard benchmarks significantly"
        score = CitationVerifier._check_claim_support(citation, abstract)
        assert score > 0.3

    def test_no_claim_text(self):
        score = CitationVerifier._check_claim_support({}, "some abstract")
        assert score == 0.5

    def test_no_abstract(self):
        score = CitationVerifier._check_claim_support({"claim_text": "test"}, "")
        assert score == 0.5


@pytest.mark.asyncio
class TestVerify:
    async def test_no_citations_returns_zero(self, verifier):
        result = await verifier.verify({"no_citations": True}, {})
        assert result.score == 0.0
        assert len(result.errors) > 0

    @patch("backend.verification.citation_verifier.CitationVerifier._resolve_doi")
    @patch("backend.verification.citation_verifier.CitationVerifier._query_openalex")
    @patch("backend.verification.citation_verifier.CitationVerifier._query_semantic_scholar")
    async def test_single_citation_with_mocked_apis(
        self, mock_ss, mock_oa, mock_doi, verifier,
    ):
        mock_doi.return_value = {"score": 1.0, "resolved": True, "title": "Test", "doi": "10.1234/test"}
        mock_oa.return_value = {"score": 0.9, "source": "openalex", "matched_title": "Test", "similarity": 0.9, "abstract": "Test abstract", "year": 2024}
        mock_ss.return_value = {"score": 0.5, "source": "semantic_scholar"}

        task_result = {
            "citations": [{"title": "Test Paper", "doi": "10.1234/test", "year": 2024}],
        }
        result = await verifier.verify(task_result, {"domain": "general"})
        assert result.score > 0.0
        assert result.verifier_name == "citation_reference"

    async def test_caps_at_max_citations(self, verifier):
        # 15 citations should be capped to 10
        task_result = {
            "citations": [{"title": f"Paper {i}"} for i in range(15)],
        }
        # We just verify it doesn't crash — actual API calls will fail gracefully
        result = await verifier.verify(task_result, {"domain": "general"})
        assert result.details.get("citations_checked", 0) <= 10

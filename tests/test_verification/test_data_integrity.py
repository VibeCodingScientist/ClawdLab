"""Tests for data integrity cross-cutting verifier."""
import pytest
import hashlib
import json

from backend.verification.data_integrity import DataIntegrityVerifier


@pytest.fixture
def verifier():
    return DataIntegrityVerifier()


class TestApplicability:
    def test_applicable_with_data(self, verifier):
        assert verifier.is_applicable({"data": [{"a": 1}]}, {}) is True

    def test_applicable_with_dataset(self, verifier):
        assert verifier.is_applicable({"dataset": [{"a": 1}]}, {}) is True

    def test_applicable_with_raw_data(self, verifier):
        assert verifier.is_applicable({"raw_data": [{"a": 1}]}, {}) is True

    def test_applicable_with_results_summary(self, verifier):
        assert verifier.is_applicable({"results_summary": {"mean": 3.5}}, {}) is True

    def test_applicable_with_checksums(self, verifier):
        assert verifier.is_applicable({"output_checksums": {"file.csv": "abc123"}}, {}) is True

    def test_not_applicable_empty(self, verifier):
        assert verifier.is_applicable({}, {}) is False


class TestExtractData:
    def test_extract_from_list(self):
        data = DataIntegrityVerifier._extract_data({"data": [{"a": 1}, {"a": 2}]})
        assert len(data) == 2

    def test_extract_from_dict_with_rows(self):
        data = DataIntegrityVerifier._extract_data({"data": {"rows": [{"a": 1}]}})
        assert len(data) == 1

    def test_extract_from_results_summary(self):
        data = DataIntegrityVerifier._extract_data({"results_summary": {"mean": 3.5, "std": 1.2}})
        assert data is not None
        assert len(data) == 1

    def test_extract_returns_none_for_empty(self):
        data = DataIntegrityVerifier._extract_data({})
        assert data is None


class TestSchemaCheck:
    def test_consistent_schema(self):
        data = [{"a": 1, "b": 2}, {"a": 3, "b": 4}, {"a": 5, "b": 6}]
        result = DataIntegrityVerifier._check_schema(data, None)
        assert result["score"] == 1.0

    def test_inconsistent_schema(self):
        data = [{"a": 1, "b": 2}, {"a": 3, "c": 4}, {"a": 5, "b": 6}]
        result = DataIntegrityVerifier._check_schema(data, None)
        assert result["score"] < 1.0
        assert result["inconsistent_rows"] > 0

    def test_explicit_schema_match(self):
        data = [{"a": 1, "b": 2}]
        schema = {"fields": ["a", "b"]}
        result = DataIntegrityVerifier._check_schema(data, schema)
        assert result["score"] == 1.0

    def test_explicit_schema_missing_fields(self):
        data = [{"a": 1}]
        schema = {"fields": ["a", "b", "c"]}
        result = DataIntegrityVerifier._check_schema(data, schema)
        assert result["score"] < 1.0
        assert "b" in result["missing_fields"]

    def test_single_row(self):
        data = [{"a": 1}]
        result = DataIntegrityVerifier._check_schema(data, None)
        assert result["score"] == 1.0

    def test_empty_data(self):
        result = DataIntegrityVerifier._check_schema([], None)
        assert result["applicable"] is False


class TestDuplicateCheck:
    def test_no_duplicates(self):
        data = [{"a": 1}, {"a": 2}, {"a": 3}]
        result = DataIntegrityVerifier._check_duplicates(data)
        assert result["score"] == 1.0
        assert result["exact_duplicates"] == 0

    def test_some_duplicates(self):
        data = [{"a": 1}, {"a": 1}, {"a": 2}, {"a": 3}]
        result = DataIntegrityVerifier._check_duplicates(data)
        assert result["exact_duplicates"] == 1
        assert result["score"] < 1.0

    def test_all_duplicates(self):
        data = [{"a": 1}] * 10
        result = DataIntegrityVerifier._check_duplicates(data)
        assert result["score"] < 0.5
        assert result["exact_duplicates"] == 9

    def test_single_row(self):
        data = [{"a": 1}]
        result = DataIntegrityVerifier._check_duplicates(data)
        assert result["score"] == 1.0


class TestOutlierCheck:
    def test_no_outliers(self):
        data = [{"x": float(i)} for i in range(100)]
        result = DataIntegrityVerifier._check_outliers(data)
        assert result["score"] >= 0.8

    def test_with_outliers(self):
        data = [{"x": float(i)} for i in range(100)]
        data.extend([{"x": 1000.0}] * 20)  # Add many extreme outliers
        result = DataIntegrityVerifier._check_outliers(data)
        assert result["total_outliers"] > 0

    def test_no_numeric_data(self):
        data = [{"name": "Alice"}, {"name": "Bob"}]
        result = DataIntegrityVerifier._check_outliers(data)
        assert result["applicable"] is False

    def test_empty_data(self):
        result = DataIntegrityVerifier._check_outliers([])
        assert result["applicable"] is False


class TestHashCheck:
    def test_matching_hash(self):
        data_blob = {"key": "value"}
        serialised = json.dumps(data_blob, sort_keys=True, separators=(",", ":"), default=str)
        expected_hash = hashlib.sha256(serialised.encode()).hexdigest()

        result = DataIntegrityVerifier._check_hashes(
            {"my_data": data_blob},
            {"my_data": expected_hash},
        )
        assert result["score"] == 1.0

    def test_mismatched_hash(self):
        result = DataIntegrityVerifier._check_hashes(
            {"my_data": "actual content"},
            {"my_data": "deadbeef" * 8},
        )
        assert result["score"] == 0.0
        assert result["mismatches"] == 1

    def test_missing_data(self):
        result = DataIntegrityVerifier._check_hashes(
            {},
            {"missing_key": "abc123"},
        )
        assert result["score"] == 0.0

    def test_no_checksums(self):
        result = DataIntegrityVerifier._check_hashes({}, {})
        assert result["applicable"] is False


@pytest.mark.asyncio
class TestVerify:
    async def test_with_clean_data(self, verifier):
        task_result = {
            "data": [{"x": float(i), "y": float(i * 2)} for i in range(50)],
        }
        result = await verifier.verify(task_result, {})
        assert result.verifier_name == "data_integrity"
        assert result.score > 0.0

    async def test_with_duplicated_data(self, verifier):
        task_result = {
            "data": [{"x": 1, "y": 2}] * 50,
        }
        result = await verifier.verify(task_result, {})
        # Should get penalized for duplicates
        assert result.score < 1.0

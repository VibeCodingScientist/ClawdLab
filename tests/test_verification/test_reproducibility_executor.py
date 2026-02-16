"""Tests for reproducibility executor cross-cutting verifier."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from backend.verification.reproducibility_executor import ReproducibilityExecutor


@pytest.fixture
def verifier():
    return ReproducibilityExecutor()


class TestApplicability:
    def test_applicable_with_both_fields(self, verifier):
        assert verifier.is_applicable(
            {"code_repo": "https://github.com/user/repo", "code_commit": "abc123"},
            {},
        ) is True

    def test_not_applicable_missing_repo(self, verifier):
        assert verifier.is_applicable({"code_commit": "abc123"}, {}) is False

    def test_not_applicable_missing_commit(self, verifier):
        assert verifier.is_applicable({"code_repo": "https://github.com/user/repo"}, {}) is False

    def test_not_applicable_empty(self, verifier):
        assert verifier.is_applicable({}, {}) is False

    def test_requires_docker(self, verifier):
        assert verifier.requires_docker is True


class TestDetectEntryPoint:
    def test_detect_reproduce_py(self, verifier, tmp_path):
        (tmp_path / "reproduce.py").touch()
        assert verifier._detect_entry_point(tmp_path) == "reproduce.py"

    def test_detect_run_sh(self, verifier, tmp_path):
        (tmp_path / "run.sh").touch()
        assert verifier._detect_entry_point(tmp_path) == "run.sh"

    def test_detect_main_py(self, verifier, tmp_path):
        (tmp_path / "main.py").touch()
        assert verifier._detect_entry_point(tmp_path) == "main.py"

    def test_detect_makefile(self, verifier, tmp_path):
        (tmp_path / "Makefile").touch()
        assert verifier._detect_entry_point(tmp_path) == "Makefile"

    def test_priority_order(self, verifier, tmp_path):
        # reproduce.py should be preferred over main.py
        (tmp_path / "main.py").touch()
        (tmp_path / "reproduce.py").touch()
        assert verifier._detect_entry_point(tmp_path) == "reproduce.py"

    def test_no_entry_point(self, verifier, tmp_path):
        assert verifier._detect_entry_point(tmp_path) is None


class TestCheckOutputs:
    def test_numeric_match(self):
        actual = {"accuracy": 0.95, "loss": 0.05}
        claimed = {"accuracy": 0.94, "loss": 0.06}
        score, details = ReproducibilityExecutor._check_outputs(actual, claimed, {})
        assert score > 0.0
        assert details["total"] == 2

    def test_exact_match(self):
        actual = {"result": "success"}
        claimed = {"result": "success"}
        score, details = ReproducibilityExecutor._check_outputs(actual, claimed, {})
        assert score == 1.0

    def test_no_claimed_results(self):
        score, details = ReproducibilityExecutor._check_outputs({}, {}, {})
        assert score == 0.5
        assert "No claimed results" in details["note"]

    def test_missing_output_key(self):
        actual = {}
        claimed = {"accuracy": 0.95}
        score, details = ReproducibilityExecutor._check_outputs(actual, claimed, {})
        assert score == 0.0

    def test_checksum_match(self):
        import hashlib
        data = "test data"
        expected_hash = hashlib.sha256(data.encode()).hexdigest()
        actual = {"file.csv": data}
        score, details = ReproducibilityExecutor._check_outputs(actual, {}, {"file.csv": expected_hash})
        assert score == 1.0


class TestCheckDeps:
    @pytest.mark.asyncio
    async def test_requirements_txt_found(self, verifier, tmp_path):
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        (repo_path / "requirements.txt").write_text("numpy>=1.24")
        ok, detail = await verifier._check_deps(str(tmp_path))
        assert ok is True
        assert detail["score"] == 1.0
        assert "requirements.txt" in detail["found"]

    @pytest.mark.asyncio
    async def test_no_deps_found(self, verifier, tmp_path):
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        ok, detail = await verifier._check_deps(str(tmp_path))
        assert ok is False
        assert detail["score"] == 0.3


@pytest.mark.asyncio
class TestVerify:
    @patch("backend.verification.reproducibility_executor.ReproducibilityExecutor._clone_repo")
    async def test_clone_failure(self, mock_clone, verifier):
        mock_clone.return_value = (False, {"error": "Access denied", "cloned": False})

        result = await verifier.verify(
            {"code_repo": "https://github.com/user/repo", "code_commit": "abc123"},
            {},
        )
        assert result.score == 0.0
        assert len(result.errors) > 0

    @patch("backend.verification.reproducibility_executor.ReproducibilityExecutor._execute")
    @patch("backend.verification.reproducibility_executor.ReproducibilityExecutor._check_deps")
    @patch("backend.verification.reproducibility_executor.ReproducibilityExecutor._clone_repo")
    async def test_full_success(self, mock_clone, mock_deps, mock_exec, verifier):
        mock_clone.return_value = (True, {"cloned": True, "checked_out": True})
        mock_deps.return_value = (True, {"score": 1.0, "found": ["requirements.txt"]})
        mock_exec.return_value = (True, {
            "exit_code": 0,
            "entry_point": "main.py",
            "outputs": {"accuracy": 0.95},
        })

        result = await verifier.verify(
            {
                "code_repo": "https://github.com/user/repo",
                "code_commit": "abc123",
                "claimed_results": {"accuracy": 0.94},
            },
            {},
        )
        assert result.score > 0.5
        assert result.verifier_name == "reproducibility"

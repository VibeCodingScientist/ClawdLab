"""Tests for Lean 4 adapter with mocked subprocess."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.verification.base import VerificationBadge
from backend.verification.lean4_adapter import Lean4Adapter


@pytest.fixture
def adapter():
    return Lean4Adapter()


def _mock_process(returncode: int, stdout: bytes = b"", stderr: bytes = b""):
    """Create a mock async process."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


@pytest.mark.asyncio
class TestLean4Adapter:
    async def test_domain(self, adapter):
        assert adapter.domain == "mathematics"

    async def test_missing_proof_code(self, adapter):
        result = await adapter.verify({}, {})
        assert result.passed is False
        assert result.badge == VerificationBadge.RED
        assert "No proof_code" in result.errors[0]

    async def test_unknown_claim_type(self, adapter):
        result = await adapter.verify(
            {"proof_code": "some code", "claim_type": "lemma"},
            {},
        )
        assert result.passed is False
        assert "Unknown claim_type" in result.errors[0]

    @patch("backend.verification.lean4_adapter.asyncio.create_subprocess_exec")
    async def test_theorem_success(self, mock_exec, adapter):
        proc = _mock_process(0, stdout=b"Build successful")
        mock_exec.return_value = proc

        result = await adapter.verify(
            {
                "proof_code": "theorem test : True := by trivial",
                "claim_type": "theorem",
                "statement": "True",
                "dependencies": ["Mathlib.Tactic"],
            },
            {},
        )
        assert result.passed is True
        assert result.score == 1.0
        assert result.badge == VerificationBadge.GREEN
        assert result.details["compiler"] == "lean4"

    @patch("backend.verification.lean4_adapter.asyncio.create_subprocess_exec")
    async def test_theorem_failure(self, mock_exec, adapter):
        proc = _mock_process(1, stderr=b"error: type mismatch\n  expected: Nat")
        mock_exec.return_value = proc

        result = await adapter.verify(
            {"proof_code": "theorem bad : False := by sorry", "claim_type": "theorem"},
            {},
        )
        assert result.passed is False
        assert result.score == 0.0
        assert result.badge == VerificationBadge.RED
        assert len(result.errors) > 0

    @patch("backend.verification.lean4_adapter.asyncio.create_subprocess_exec")
    async def test_theorem_timeout(self, mock_exec, adapter):
        proc = MagicMock()
        proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        mock_exec.return_value = proc

        result = await adapter.verify(
            {"proof_code": "theorem slow : True := by sorry", "claim_type": "theorem"},
            {},
        )
        assert result.passed is False
        assert "timed out" in result.errors[0]

    @patch("backend.verification.lean4_adapter.asyncio.create_subprocess_exec")
    async def test_conjecture_success(self, mock_exec, adapter):
        proc = _mock_process(0)
        mock_exec.return_value = proc

        result = await adapter.verify(
            {
                "proof_code": "#check (∀ n : ℕ, n + 0 = n)",
                "claim_type": "conjecture",
                "statement": "∀ n : ℕ, n + 0 = n",
            },
            {},
        )
        assert result.passed is True
        assert result.score == 0.7
        assert result.badge == VerificationBadge.AMBER

    async def test_conjecture_no_statement(self, adapter):
        result = await adapter.verify(
            {"proof_code": "code", "claim_type": "conjecture"},
            {},
        )
        assert result.passed is False
        assert "No statement" in result.errors[0]


class TestParseMetrics:
    def test_parse_lean_metrics(self):
        adapter = Lean4Adapter()
        code = "import Mathlib\n\ntheorem test : True := by\n  simp\n  ring\n"
        metrics = adapter._parse_lean_metrics("", "", code)
        assert metrics["lines_of_code"] == 5
        assert "simp" in metrics["tactics_used"]
        assert "ring" in metrics["tactics_used"]
        assert metrics["tactic_count"] >= 2

    def test_parse_lean_metrics_no_tactics(self):
        adapter = Lean4Adapter()
        code = "import Mathlib\n\ndef foo := 42\n"
        metrics = adapter._parse_lean_metrics("", "", code)
        assert metrics["tactic_count"] == 0

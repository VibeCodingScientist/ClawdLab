"""Tests for ML live inference claim type."""
import json
import pytest
from unittest.mock import patch, AsyncMock

from backend.verification.ml_repro_adapter import MLReproAdapter


@pytest.fixture
def adapter():
    return MLReproAdapter()


class TestRequiresDockerFor:
    def test_benchmark_live_requires_docker(self, adapter):
        assert adapter.requires_docker_for({"claim_type": "benchmark_live"}) is True

    def test_benchmark_result_no_docker(self, adapter):
        assert adapter.requires_docker_for({"claim_type": "benchmark_result"}) is False

    def test_ml_experiment_no_docker(self, adapter):
        assert adapter.requires_docker_for({"claim_type": "ml_experiment"}) is False

    def test_architecture_no_docker(self, adapter):
        assert adapter.requires_docker_for({"claim_type": "architecture"}) is False


class TestBuildInferenceScript:
    def test_script_contains_model_id(self):
        script = MLReproAdapter._build_inference_script("my-model/test", "mmlu", 20)
        assert "my-model/test" in script
        assert "sample_size = 20" in script

    def test_script_is_valid_python(self):
        script = MLReproAdapter._build_inference_script("test/model", "test", 10)
        compile(script, "<test>", "exec")


@pytest.mark.asyncio
class TestBenchmarkLive:
    async def test_no_model_id(self, adapter):
        result = await adapter.verify({"claim_type": "benchmark_live"}, {})
        assert result.passed is False
        assert "model_id" in result.errors[0]

    async def test_no_benchmark(self, adapter):
        result = await adapter.verify({
            "claim_type": "benchmark_live",
            "model_id": "test/model",
        }, {})
        assert result.passed is False
        assert "benchmark" in result.errors[0]

    @patch("asyncio.create_subprocess_exec")
    async def test_docker_timeout(self, mock_exec, adapter):
        import asyncio
        mock_proc = AsyncMock()
        mock_proc.communicate.side_effect = asyncio.TimeoutError()
        mock_exec.return_value = mock_proc

        result = await adapter.verify({
            "claim_type": "benchmark_live",
            "model_id": "test/model",
            "benchmark": "mmlu",
        }, {})
        assert result.passed is False
        assert "timed out" in result.errors[0]

    @patch("asyncio.create_subprocess_exec")
    async def test_successful_inference(self, mock_exec, adapter):
        inference_output = json.dumps({
            "model_loaded": True,
            "total_samples": 20,
            "successful_samples": 18,
            "metrics": {"accuracy": 0.65},
            "avg_latency_seconds": 2.5,
        })

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (
            inference_output.encode(),
            b"",
        )
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        result = await adapter.verify({
            "claim_type": "benchmark_live",
            "model_id": "test/model",
            "benchmark": "mmlu",
            "metrics": {"accuracy": 0.65},
        }, {})
        assert result.score > 0.0
        assert result.details["claim_type"] == "benchmark_live"

    @patch("asyncio.create_subprocess_exec")
    async def test_model_load_failure(self, mock_exec, adapter):
        inference_output = json.dumps({
            "model_loaded": False,
            "error": "Model not found",
        })

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (
            inference_output.encode(),
            b"",
        )
        mock_proc.returncode = 1
        mock_exec.return_value = mock_proc

        result = await adapter.verify({
            "claim_type": "benchmark_live",
            "model_id": "nonexistent/model",
            "benchmark": "mmlu",
        }, {})
        assert result.passed is False
        assert result.score == 0.0

    @patch("asyncio.create_subprocess_exec")
    async def test_invalid_json_output(self, mock_exec, adapter):
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (
            b"not valid json",
            b"Some error occurred",
        )
        mock_proc.returncode = 1
        mock_exec.return_value = mock_proc

        result = await adapter.verify({
            "claim_type": "benchmark_live",
            "model_id": "test/model",
            "benchmark": "mmlu",
        }, {})
        assert result.passed is False
        assert "valid JSON" in result.errors[0]

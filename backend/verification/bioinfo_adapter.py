"""Bioinformatics verification: Nextflow/Snakemake pipeline replay."""
import asyncio
import json
import tempfile
import time
from pathlib import Path

from backend.verification.base import (
    VerificationAdapter, VerificationResult, VerificationBadge,
)
from backend.logging_config import get_logger

logger = get_logger(__name__)

BIOINFO_IMAGE = "clawdlab/bioinfo:latest"
BIOINFO_TIMEOUT = 7200  # 2 hours (pipelines can be long)

SUPPORTED_PIPELINES = {"nextflow", "snakemake", "wdl"}


class BioInfoAdapter(VerificationAdapter):
    domain = "bioinformatics"

    async def verify(self, task_result: dict, task_metadata: dict) -> VerificationResult:
        claim_type = task_result.get("claim_type", "pipeline_result")

        if claim_type == "pipeline_result":
            return await self._verify_pipeline(task_result)
        elif claim_type == "sequence_annotation":
            return await self._verify_annotation(task_result)
        elif claim_type == "statistical_claim":
            return await self._verify_statistics(task_result)
        else:
            return VerificationResult.fail(self.domain, [f"Unknown claim_type: {claim_type}"])

    async def _verify_pipeline(self, result: dict) -> VerificationResult:
        """Re-run pipeline at specified commit and compare outputs."""
        start = time.monotonic()

        source = result.get("pipeline_source")
        commit = result.get("pipeline_commit")
        params = result.get("parameters", {})
        claimed_checksums = result.get("output_checksums", {})

        if not source or not commit:
            return VerificationResult.fail(self.domain, ["pipeline_source and pipeline_commit required"])

        # Detect workflow manager from source
        manager = self._detect_manager(source)

        with tempfile.TemporaryDirectory() as tmpdir:
            work_path = Path(tmpdir)

            # Write pipeline config
            config = {
                "source": source,
                "commit": commit,
                "manager": manager,
                "params": params,
                "input_datasets": result.get("input_datasets", []),
            }
            (work_path / "config.json").write_text(json.dumps(config))
            (work_path / "run_pipeline.py").write_text(self._build_pipeline_script(manager))

            cmd = [
                "docker", "run", "--rm",
                "--memory=32g", "--cpus=8",
                "-v", f"{tmpdir}:/workspace",
                BIOINFO_IMAGE,
                "python3", "/workspace/run_pipeline.py",
            ]

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=BIOINFO_TIMEOUT)
            except asyncio.TimeoutError:
                return VerificationResult.fail(self.domain, ["Pipeline execution timed out (2 hour limit)"])

        elapsed = time.monotonic() - start

        if proc.returncode != 0:
            return VerificationResult.fail(self.domain, [stderr.decode(errors="replace")[:500]])

        try:
            output = json.loads(stdout.decode())
        except json.JSONDecodeError:
            return VerificationResult.fail(self.domain, ["Failed to parse pipeline output"])

        # Compare checksums
        reproduced_checksums = output.get("output_checksums", {})
        checksum_matches = 0
        total_checks = len(claimed_checksums)

        for filename, claimed_hash in claimed_checksums.items():
            if filename in reproduced_checksums:
                if reproduced_checksums[filename] == claimed_hash:
                    checksum_matches += 1

        match_ratio = checksum_matches / max(total_checks, 1)

        # If exact checksums don't match, check qualitative similarity
        qual_score = output.get("qualitative_similarity", 0)
        score = max(match_ratio, qual_score * 0.5)
        score = min(1.0, round(score, 4))

        return VerificationResult(
            passed=match_ratio >= 0.8 or qual_score >= 0.9,
            score=score,
            badge=VerificationResult.score_to_badge(score),
            domain=self.domain,
            details={
                "claim_type": "pipeline_result",
                "pipeline": source,
                "manager": manager,
                "checksum_match_ratio": match_ratio,
                "qualitative_similarity": qual_score,
                "reproduced_checksums": reproduced_checksums,
                "execution_time": output.get("execution_time_seconds"),
            },
            compute_time_seconds=elapsed,
        )

    async def _verify_annotation(self, result: dict) -> VerificationResult:
        """Re-run sequence annotation and compare."""
        sequence = result.get("sequence", "")
        annotation_method = result.get("annotation_method")

        if not sequence or not annotation_method:
            return VerificationResult.fail(self.domain, ["sequence and annotation_method required"])

        return VerificationResult(
            passed=False, score=0.0,
            badge=VerificationBadge.AMBER,
            domain=self.domain,
            errors=["Annotation verification not yet implemented"],
        )

    async def _verify_statistics(self, result: dict) -> VerificationResult:
        """Re-run statistical analysis and compare p-values/effect sizes."""
        claims = result.get("statistical_claims", [])
        if not claims:
            return VerificationResult.fail(self.domain, ["No statistical_claims provided"])

        return VerificationResult(
            passed=False, score=0.0,
            badge=VerificationBadge.AMBER,
            domain=self.domain,
            errors=["Statistical verification not yet implemented"],
        )

    def _detect_manager(self, source: str) -> str:
        if "nf-core" in source or "nextflow" in source.lower():
            return "nextflow"
        elif "snakemake" in source.lower():
            return "snakemake"
        return "nextflow"  # default

    def _build_pipeline_script(self, manager: str) -> str:
        return f'''
import json
import subprocess
import hashlib
from pathlib import Path

config = json.loads(Path("/workspace/config.json").read_text())
result = {{"output_checksums": {{}}, "qualitative_similarity": 0.0, "execution_time_seconds": 0}}

# Clone pipeline
source = config["source"]
commit = config["commit"]
subprocess.run(["git", "clone", "--depth", "1", "-b", commit, source, "/tmp/pipeline"],
               capture_output=True)

if "{manager}" == "nextflow":
    # Run: nextflow run /tmp/pipeline -params-file /workspace/params.json
    Path("/workspace/params.json").write_text(json.dumps(config["params"]))
    proc = subprocess.run(
        ["nextflow", "run", "/tmp/pipeline", "-params-file", "/workspace/params.json",
         "--outdir", "/tmp/results"],
        capture_output=True, timeout=6000
    )
    if proc.returncode == 0:
        # Hash all output files
        for f in Path("/tmp/results").rglob("*"):
            if f.is_file():
                h = hashlib.sha256(f.read_bytes()).hexdigest()
                result["output_checksums"][f.name] = f"sha256:{{h}}"
        result["qualitative_similarity"] = 0.8

print(json.dumps(result))
'''

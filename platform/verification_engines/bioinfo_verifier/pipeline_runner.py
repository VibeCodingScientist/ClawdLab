"""Pipeline execution service for Nextflow and Snakemake."""

import asyncio
import hashlib
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from platform.verification_engines.bioinfo_verifier.base import (
    BaseBioinfoVerifier,
    MCPToolProvider,
    PipelineConfig,
    PipelineOutput,
    PipelineResult,
    PipelineStatus,
)
from platform.verification_engines.bioinfo_verifier.config import (
    PIPELINE_TYPES,
    get_settings,
)
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class PipelineRunner(BaseBioinfoVerifier):
    """
    Execute bioinformatics pipelines in sandboxed containers.

    Supports:
    - Nextflow workflows
    - Snakemake workflows
    - WDL/Cromwell (future)
    """

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """Initialize pipeline runner."""
        super().__init__(tool_provider)
        self._work_dir_base = Path("/tmp/bioinfo_pipelines")
        self._work_dir_base.mkdir(parents=True, exist_ok=True)

    @property
    def component_name(self) -> str:
        return "pipeline_runner"

    async def verify(
        self,
        config: PipelineConfig,
    ) -> PipelineResult:
        """Run a pipeline and return results."""
        return await self.run_pipeline(config)

    async def run_pipeline(
        self,
        config: PipelineConfig,
        work_dir: str | None = None,
    ) -> PipelineResult:
        """
        Execute a bioinformatics pipeline.

        Args:
            config: Pipeline configuration
            work_dir: Working directory (created if not provided)

        Returns:
            PipelineResult with execution status and outputs
        """
        start_time = datetime.utcnow()

        # Validate engine
        if config.engine not in PIPELINE_TYPES:
            return PipelineResult(
                status=PipelineStatus.FAILED,
                exit_code=1,
                error_message=f"Unknown pipeline engine: {config.engine}",
            )

        engine_config = PIPELINE_TYPES[config.engine]

        # Try MCP tool first
        if settings.mcp_enabled:
            mcp_tool = engine_config.get("mcp_tool_name")
            if mcp_tool and await self._has_tool(mcp_tool):
                return await self._run_via_mcp(config, mcp_tool)

        # Fall back to local execution
        if config.engine == "nextflow":
            result = await self._run_nextflow(config, work_dir)
        elif config.engine == "snakemake":
            result = await self._run_snakemake(config, work_dir)
        else:
            result = PipelineResult(
                status=PipelineStatus.FAILED,
                exit_code=1,
                error_message=f"Engine not implemented: {config.engine}",
            )

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        result.execution_time_seconds = elapsed

        return result

    async def _run_via_mcp(
        self,
        config: PipelineConfig,
        tool_name: str,
    ) -> PipelineResult:
        """Run pipeline using MCP tool."""
        try:
            result = await self._invoke_tool(
                tool_name=tool_name,
                parameters={
                    "workflow_url": config.workflow_url,
                    "version": config.version,
                    "parameters": config.parameters,
                    "profiles": config.profiles,
                    "resume": config.resume,
                },
                timeout=settings.pipeline_timeout,
            )

            outputs = [
                PipelineOutput(
                    name=o.get("name", ""),
                    path=o.get("path", ""),
                    file_type=o.get("file_type", ""),
                    size_bytes=o.get("size_bytes"),
                    checksum=o.get("checksum"),
                )
                for o in result.get("outputs", [])
            ]

            return PipelineResult(
                status=PipelineStatus.COMPLETED if result.get("success") else PipelineStatus.FAILED,
                exit_code=result.get("exit_code", 0),
                outputs=outputs,
                logs=result.get("logs", ""),
                execution_time_seconds=result.get("execution_time", 0),
                resource_usage=result.get("resource_usage", {}),
            )

        except Exception as e:
            logger.warning("mcp_pipeline_error", tool=tool_name, error=str(e))
            return PipelineResult(
                status=PipelineStatus.FAILED,
                exit_code=1,
                error_message=str(e),
            )

    async def _run_nextflow(
        self,
        config: PipelineConfig,
        work_dir: str | None = None,
    ) -> PipelineResult:
        """Run Nextflow workflow."""
        # Create working directory
        if work_dir:
            wdir = Path(work_dir)
        else:
            run_id = hashlib.md5(
                f"{config.workflow_url}-{datetime.utcnow().isoformat()}".encode()
            ).hexdigest()[:12]
            wdir = self._work_dir_base / f"nf_{run_id}"

        wdir.mkdir(parents=True, exist_ok=True)

        # Build Nextflow command
        cmd = ["nextflow", "run", config.workflow_url]

        # Add version/revision
        if config.version:
            cmd.extend(["-r", config.version])

        # Add profiles
        if config.profiles:
            cmd.extend(["-profile", ",".join(config.profiles)])

        # Add parameters
        for key, value in config.parameters.items():
            if isinstance(value, bool):
                if value:
                    cmd.append(f"--{key}")
            else:
                cmd.extend([f"--{key}", str(value)])

        # Add config files
        for cfg in config.config_files:
            cmd.extend(["-c", cfg])

        # Add resume flag
        if config.resume:
            cmd.append("-resume")

        # Set work directory
        cmd.extend(["-w", str(wdir / "work")])

        logger.info("nextflow_starting", workflow=config.workflow_url, work_dir=str(wdir))

        # Execute via Singularity
        if settings.use_singularity:
            full_cmd = [
                "singularity", "exec",
                "-B", f"{wdir}:{wdir}",
                settings.singularity_image_path,
            ] + cmd
        else:
            full_cmd = cmd

        try:
            process = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(wdir),
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.pipeline_timeout,
            )

            logs = stdout.decode() + "\n" + stderr.decode()

            if process.returncode == 0:
                outputs = await self._collect_outputs(wdir)
                status = PipelineStatus.COMPLETED
            else:
                outputs = []
                status = PipelineStatus.FAILED

            return PipelineResult(
                status=status,
                exit_code=process.returncode,
                outputs=outputs,
                logs=logs,
                work_dir=str(wdir),
                error_message=stderr.decode() if process.returncode != 0 else None,
            )

        except asyncio.TimeoutError:
            return PipelineResult(
                status=PipelineStatus.TIMEOUT,
                exit_code=-1,
                error_message=f"Pipeline timed out after {settings.pipeline_timeout}s",
                work_dir=str(wdir),
            )
        except Exception as e:
            return PipelineResult(
                status=PipelineStatus.FAILED,
                exit_code=-1,
                error_message=str(e),
                work_dir=str(wdir),
            )

    async def _run_snakemake(
        self,
        config: PipelineConfig,
        work_dir: str | None = None,
    ) -> PipelineResult:
        """Run Snakemake workflow."""
        # Create working directory
        if work_dir:
            wdir = Path(work_dir)
        else:
            run_id = hashlib.md5(
                f"{config.workflow_url}-{datetime.utcnow().isoformat()}".encode()
            ).hexdigest()[:12]
            wdir = self._work_dir_base / f"smk_{run_id}"

        wdir.mkdir(parents=True, exist_ok=True)

        # Clone workflow if URL
        if config.workflow_url.startswith(("http://", "https://", "git@")):
            clone_cmd = ["git", "clone"]
            if config.version:
                clone_cmd.extend(["--branch", config.version])
            clone_cmd.extend([config.workflow_url, str(wdir / "workflow")])

            process = await asyncio.create_subprocess_exec(
                *clone_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            snakefile = wdir / "workflow" / "Snakefile"
        else:
            snakefile = Path(config.workflow_url)

        # Build Snakemake command
        cmd = [
            "snakemake",
            "--snakefile", str(snakefile),
            "--cores", str(settings.max_cpus),
            "--directory", str(wdir),
        ]

        # Add config values
        if config.parameters:
            config_items = [f"{k}={v}" for k, v in config.parameters.items()]
            cmd.extend(["--config"] + config_items)

        # Add profiles
        for profile in config.profiles:
            cmd.extend(["--profile", profile])

        logger.info("snakemake_starting", workflow=config.workflow_url, work_dir=str(wdir))

        # Execute via Singularity
        if settings.use_singularity:
            full_cmd = [
                "singularity", "exec",
                "-B", f"{wdir}:{wdir}",
                settings.singularity_image_path,
            ] + cmd
        else:
            full_cmd = cmd

        try:
            process = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(wdir),
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.pipeline_timeout,
            )

            logs = stdout.decode() + "\n" + stderr.decode()

            if process.returncode == 0:
                outputs = await self._collect_outputs(wdir)
                status = PipelineStatus.COMPLETED
            else:
                outputs = []
                status = PipelineStatus.FAILED

            return PipelineResult(
                status=status,
                exit_code=process.returncode,
                outputs=outputs,
                logs=logs,
                work_dir=str(wdir),
                error_message=stderr.decode() if process.returncode != 0 else None,
            )

        except asyncio.TimeoutError:
            return PipelineResult(
                status=PipelineStatus.TIMEOUT,
                exit_code=-1,
                error_message=f"Pipeline timed out after {settings.pipeline_timeout}s",
                work_dir=str(wdir),
            )
        except Exception as e:
            return PipelineResult(
                status=PipelineStatus.FAILED,
                exit_code=-1,
                error_message=str(e),
                work_dir=str(wdir),
            )

    async def _collect_outputs(self, work_dir: Path) -> list[PipelineOutput]:
        """Collect outputs from pipeline execution."""
        outputs = []

        # Look for common output directories
        output_dirs = ["results", "output", "outputs", "results_final"]
        for dir_name in output_dirs:
            output_path = work_dir / dir_name
            if output_path.exists():
                for file_path in output_path.rglob("*"):
                    if file_path.is_file():
                        outputs.append(await self._create_output(file_path))

        return outputs

    async def _create_output(self, file_path: Path) -> PipelineOutput:
        """Create PipelineOutput from file."""
        stat = file_path.stat()
        file_type = self._detect_file_type(file_path)

        # Calculate checksum for small files
        checksum = None
        if stat.st_size < 100 * 1024 * 1024:  # < 100MB
            checksum = await self._calculate_checksum(file_path)

        return PipelineOutput(
            name=file_path.name,
            path=str(file_path),
            file_type=file_type,
            size_bytes=stat.st_size,
            checksum=checksum,
        )

    def _detect_file_type(self, file_path: Path) -> str:
        """Detect file type from extension."""
        suffix = file_path.suffix.lower()
        file_types = {
            ".bam": "bam",
            ".cram": "cram",
            ".vcf": "vcf",
            ".bed": "bed",
            ".gff": "gff",
            ".gtf": "gtf",
            ".fa": "fasta",
            ".fasta": "fasta",
            ".fq": "fastq",
            ".fastq": "fastq",
            ".tsv": "tsv",
            ".csv": "csv",
            ".txt": "text",
            ".json": "json",
            ".html": "html",
            ".pdf": "pdf",
            ".png": "image",
            ".jpg": "image",
        }
        return file_types.get(suffix, "unknown")

    async def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate MD5 checksum of file."""
        md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        return md5.hexdigest()

    async def validate_workflow(
        self,
        config: PipelineConfig,
    ) -> dict[str, Any]:
        """
        Validate a workflow configuration without running it.

        Args:
            config: Pipeline configuration

        Returns:
            Dict with validation results
        """
        issues = []
        warnings = []

        # Check engine
        if config.engine not in PIPELINE_TYPES:
            issues.append(f"Unknown engine: {config.engine}")

        # Check workflow URL
        if not config.workflow_url:
            issues.append("Workflow URL is required")

        # Check parameters
        if config.parameters:
            for key, value in config.parameters.items():
                if value is None:
                    warnings.append(f"Parameter '{key}' has null value")

        # Check profiles
        for profile in config.profiles:
            if not profile:
                warnings.append("Empty profile specified")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "engine": config.engine,
        }

    def get_supported_engines(self) -> list[dict[str, Any]]:
        """Get list of supported pipeline engines."""
        return [
            {
                "id": engine_id,
                "name": config["name"],
                "description": config["description"],
            }
            for engine_id, config in PIPELINE_TYPES.items()
        ]

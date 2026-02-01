"""Environment reproducibility system for ML experiments."""

import asyncio
import hashlib
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from platform.verification_engines.ml_verifier.base import (
    BaseEnvironmentBuilder,
    EnvironmentResult,
)
from platform.verification_engines.ml_verifier.config import ML_FRAMEWORKS, get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class DockerEnvironmentBuilder(BaseEnvironmentBuilder):
    """
    Builds reproducible Docker environments for ML experiments.

    Features:
    - Multi-stage builds for efficiency
    - CUDA/cuDNN support
    - Caching of base images
    - Deterministic layer ordering
    """

    def __init__(self, registry: str | None = None):
        """
        Initialize Docker environment builder.

        Args:
            registry: Container registry to use
        """
        self._registry = registry or settings.container_registry

    @property
    def environment_type(self) -> str:
        return "docker"

    async def build(
        self,
        specification: dict[str, Any],
        working_dir: str,
    ) -> EnvironmentResult:
        """
        Build Docker environment from specification.

        Args:
            specification: Environment specification including:
                - framework: ML framework (pytorch, tensorflow, jax)
                - requirements: List of pip packages
                - dockerfile: Optional custom Dockerfile
                - cuda_version: CUDA version needed
            working_dir: Directory containing the code

        Returns:
            EnvironmentResult with build details
        """
        started_at = datetime.utcnow()

        framework = specification.get("framework", "pytorch")
        requirements = specification.get("requirements", [])
        custom_dockerfile = specification.get("dockerfile")
        cuda_version = specification.get("cuda_version", "12.1")

        try:
            # Generate Dockerfile
            if custom_dockerfile:
                dockerfile_content = custom_dockerfile
            else:
                dockerfile_content = self._generate_dockerfile(
                    framework=framework,
                    requirements=requirements,
                    cuda_version=cuda_version,
                )

            # Write Dockerfile
            dockerfile_path = Path(working_dir) / "Dockerfile.verification"
            dockerfile_path.write_text(dockerfile_content)

            # Generate image tag
            image_hash = hashlib.sha256(dockerfile_content.encode()).hexdigest()[:12]
            image_tag = f"{self._registry}/ml-verify:{image_hash}"

            # Build image
            build_result = await self._build_image(
                dockerfile_path=str(dockerfile_path),
                context_path=working_dir,
                image_tag=image_tag,
            )

            if not build_result["success"]:
                return EnvironmentResult(
                    passed=False,
                    message=f"Docker build failed: {build_result['error']}",
                    error=build_result["error"],
                    environment_type="docker",
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            return EnvironmentResult(
                passed=True,
                message="Docker environment built successfully",
                environment_type="docker",
                image_hash=image_hash,
                build_time_seconds=build_result["build_time"],
                dependencies_installed=requirements,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.exception("docker_build_error", error=str(e))
            return EnvironmentResult(
                passed=False,
                message=f"Docker build error: {str(e)}",
                error=str(e),
                environment_type="docker",
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    def _generate_dockerfile(
        self,
        framework: str,
        requirements: list[str],
        cuda_version: str,
    ) -> str:
        """Generate Dockerfile for ML environment."""
        framework_config = ML_FRAMEWORKS.get(framework, ML_FRAMEWORKS["pytorch"])
        base_image = framework_config["base_image"]

        dockerfile = f"""# Auto-generated Dockerfile for ML verification
FROM {base_image}

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PIP_NO_CACHE_DIR=1 \\
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \\
    git \\
    wget \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Create workspace
WORKDIR /workspace

# Copy requirements and install Python dependencies
"""
        if requirements:
            req_str = "\n".join(requirements)
            dockerfile += f"""
RUN echo '{req_str}' > /tmp/requirements.txt && \\
    pip install --no-cache-dir -r /tmp/requirements.txt
"""
        dockerfile += """
# Copy code
COPY . /workspace/

# Set default command
CMD ["python", "main.py"]
"""
        return dockerfile

    async def _build_image(
        self,
        dockerfile_path: str,
        context_path: str,
        image_tag: str,
    ) -> dict[str, Any]:
        """Build Docker image."""
        start_time = datetime.utcnow()

        cmd = [
            "docker", "build",
            "-f", dockerfile_path,
            "-t", image_tag,
            "--network", "host",
            context_path,
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.max_build_time_seconds,
            )

            build_time = (datetime.utcnow() - start_time).total_seconds()

            if process.returncode != 0:
                return {
                    "success": False,
                    "error": stderr.decode("utf-8"),
                    "build_time": build_time,
                }

            return {
                "success": True,
                "image_tag": image_tag,
                "build_time": build_time,
                "output": stdout.decode("utf-8"),
            }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Build timed out",
                "build_time": settings.max_build_time_seconds,
            }

    async def cleanup(self, environment_id: str) -> None:
        """Remove Docker image."""
        cmd = ["docker", "rmi", "-f", environment_id]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()


class NixEnvironmentBuilder(BaseEnvironmentBuilder):
    """
    Builds reproducible Nix flake environments for ML experiments.

    Features:
    - Pure, reproducible builds
    - Automatic flake.nix generation
    - CUDA support via nixpkgs
    - Caching via Nix store
    """

    @property
    def environment_type(self) -> str:
        return "nix"

    async def build(
        self,
        specification: dict[str, Any],
        working_dir: str,
    ) -> EnvironmentResult:
        """
        Build Nix flake environment.

        Args:
            specification: Environment specification including:
                - flake_nix: Custom flake.nix content
                - python_packages: Python packages to include
                - system_packages: System packages to include
                - cuda: Whether CUDA is needed
            working_dir: Directory containing the code

        Returns:
            EnvironmentResult with build details
        """
        started_at = datetime.utcnow()

        custom_flake = specification.get("flake_nix")
        python_packages = specification.get("python_packages", [])
        system_packages = specification.get("system_packages", [])
        needs_cuda = specification.get("cuda", True)

        try:
            # Generate or use flake.nix
            flake_path = Path(working_dir) / "flake.nix"
            if custom_flake:
                flake_content = custom_flake
            else:
                flake_content = self._generate_flake(
                    python_packages=python_packages,
                    system_packages=system_packages,
                    cuda=needs_cuda,
                )

            flake_path.write_text(flake_content)

            # Build the flake
            build_result = await self._build_flake(working_dir)

            if not build_result["success"]:
                return EnvironmentResult(
                    passed=False,
                    message=f"Nix build failed: {build_result['error']}",
                    error=build_result["error"],
                    environment_type="nix",
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            return EnvironmentResult(
                passed=True,
                message="Nix environment built successfully",
                environment_type="nix",
                image_hash=build_result["store_path_hash"],
                build_time_seconds=build_result["build_time"],
                dependencies_installed=python_packages + system_packages,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.exception("nix_build_error", error=str(e))
            return EnvironmentResult(
                passed=False,
                message=f"Nix build error: {str(e)}",
                error=str(e),
                environment_type="nix",
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    def _generate_flake(
        self,
        python_packages: list[str],
        system_packages: list[str],
        cuda: bool,
    ) -> str:
        """Generate flake.nix for ML environment."""
        cuda_overlay = ""
        cuda_packages = ""
        if cuda:
            cuda_overlay = """
      # CUDA overlay
      cudaOverlay = final: prev: {
        cudaPackages = prev.cudaPackages_12_1;
      };"""
            cuda_packages = """
            cudaPackages.cudatoolkit
            cudaPackages.cudnn"""

        python_pkgs = "\n            ".join(
            [f"python311Packages.{pkg}" for pkg in python_packages]
        )
        system_pkgs = "\n          ".join(system_packages)

        return f"""{{
  description = "ML Verification Environment";

  inputs = {{
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-23.11";
    flake-utils.url = "github:numtide/flake-utils";
  }};

  outputs = {{ self, nixpkgs, flake-utils }}:
    flake-utils.lib.eachDefaultSystem (system:
      let{cuda_overlay}
        pkgs = import nixpkgs {{
          inherit system;
          config.allowUnfree = true;
          config.cudaSupport = {str(cuda).lower()};
        }};
      in {{
        devShells.default = pkgs.mkShell {{
          buildInputs = with pkgs; [
            python311
            python311Packages.pip
            python311Packages.virtualenv
            {python_pkgs}
            {system_pkgs}{cuda_packages}
          ];

          shellHook = ''
            export PYTHONPATH="$PWD:$PYTHONPATH"
            export LD_LIBRARY_PATH="${{pkgs.lib.makeLibraryPath [pkgs.stdenv.cc.cc]}}"
          '';
        }};
      }}
    );
}}
"""

    async def _build_flake(self, working_dir: str) -> dict[str, Any]:
        """Build Nix flake."""
        start_time = datetime.utcnow()

        cmd = ["nix", "build", "--no-link", "--print-out-paths"]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.max_build_time_seconds,
            )

            build_time = (datetime.utcnow() - start_time).total_seconds()

            if process.returncode != 0:
                return {
                    "success": False,
                    "error": stderr.decode("utf-8"),
                    "build_time": build_time,
                }

            store_path = stdout.decode("utf-8").strip()
            store_path_hash = store_path.split("/")[-1].split("-")[0] if store_path else ""

            return {
                "success": True,
                "store_path": store_path,
                "store_path_hash": store_path_hash,
                "build_time": build_time,
            }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": "Build timed out",
                "build_time": settings.max_build_time_seconds,
            }

    async def cleanup(self, environment_id: str) -> None:
        """Nix garbage collection for old paths."""
        # Nix handles cleanup through garbage collection
        pass


class EnvironmentManager:
    """
    Manages environment building for ML verification.

    Orchestrates Docker and Nix builders based on repository contents.
    """

    def __init__(self):
        """Initialize environment manager."""
        self.docker_builder = DockerEnvironmentBuilder()
        self.nix_builder = NixEnvironmentBuilder()

    async def build_environment(
        self,
        repo_path: str,
        requirements: dict[str, Any],
        preferred_type: str | None = None,
    ) -> EnvironmentResult:
        """
        Build environment for ML experiment.

        Args:
            repo_path: Path to cloned repository
            requirements: Extracted requirements from repository
            preferred_type: Preferred environment type (docker/nix)

        Returns:
            EnvironmentResult with build details
        """
        # Determine environment type
        env_type = self._determine_environment_type(requirements, preferred_type)

        if env_type == "docker":
            spec = self._prepare_docker_spec(requirements)
            return await self.docker_builder.build(spec, repo_path)
        elif env_type == "nix":
            spec = self._prepare_nix_spec(requirements)
            return await self.nix_builder.build(spec, repo_path)
        else:
            return EnvironmentResult(
                passed=False,
                message=f"Unsupported environment type: {env_type}",
                error="unsupported_environment",
                environment_type=env_type,
            )

    def _determine_environment_type(
        self,
        requirements: dict[str, Any],
        preferred_type: str | None,
    ) -> str:
        """Determine which environment type to use."""
        # If preferred type specified, use it
        if preferred_type:
            return preferred_type

        # If Dockerfile exists, use Docker
        if requirements.get("docker"):
            return "docker"

        # If flake.nix exists, use Nix
        if requirements.get("nix"):
            return "nix"

        # Default to Docker for compatibility
        if settings.docker_enabled:
            return "docker"

        if settings.nix_enabled:
            return "nix"

        return "docker"

    def _prepare_docker_spec(self, requirements: dict[str, Any]) -> dict[str, Any]:
        """Prepare Docker build specification."""
        return {
            "framework": self._detect_framework(requirements),
            "requirements": requirements.get("pip", []),
            "dockerfile": requirements.get("docker"),
            "cuda_version": "12.1",
        }

    def _prepare_nix_spec(self, requirements: dict[str, Any]) -> dict[str, Any]:
        """Prepare Nix build specification."""
        # Convert pip packages to Nix package names (simplified)
        python_packages = []
        for pkg in requirements.get("pip", []):
            # Extract package name without version
            pkg_name = pkg.split("==")[0].split(">=")[0].split("<=")[0].strip()
            python_packages.append(pkg_name.lower().replace("-", ""))

        return {
            "flake_nix": requirements.get("nix"),
            "python_packages": python_packages,
            "system_packages": ["git", "wget", "curl"],
            "cuda": True,
        }

    def _detect_framework(self, requirements: dict[str, Any]) -> str:
        """Detect ML framework from requirements."""
        pip_deps = " ".join(requirements.get("pip", [])).lower()

        if "jax" in pip_deps:
            return "jax"
        elif "tensorflow" in pip_deps:
            return "tensorflow"
        elif "transformers" in pip_deps:
            return "transformers"
        else:
            return "pytorch"  # Default

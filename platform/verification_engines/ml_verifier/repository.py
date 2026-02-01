"""Git repository cloning and verification for ML experiments."""

import asyncio
import hashlib
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from platform.verification_engines.ml_verifier.base import (
    BaseMLVerifier,
    CloneResult,
)
from platform.verification_engines.ml_verifier.config import get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class GitRepoCloner(BaseMLVerifier):
    """
    Clones and verifies ML experiment repositories.

    Features:
    - Secure URL validation
    - Commit hash verification
    - Submodule handling
    - Repository size limits
    - File integrity checking
    """

    def __init__(self, workspace_dir: str | None = None):
        """
        Initialize the repository cloner.

        Args:
            workspace_dir: Base directory for cloned repos
        """
        self._workspace_dir = workspace_dir or "/workspace/repos"
        os.makedirs(self._workspace_dir, exist_ok=True)

    @property
    def component_name(self) -> str:
        return "git_repo_cloner"

    async def verify(
        self,
        repo_url: str,
        commit_hash: str | None = None,
        branch: str | None = None,
    ) -> CloneResult:
        """
        Clone and verify a repository.

        Args:
            repo_url: Git repository URL
            commit_hash: Specific commit to checkout
            branch: Branch to clone (default: main/master)

        Returns:
            CloneResult with cloning details
        """
        started_at = datetime.utcnow()

        # Validate URL
        validation = self._validate_url(repo_url)
        if not validation["valid"]:
            return CloneResult(
                passed=False,
                message=f"Invalid repository URL: {validation['error']}",
                error=validation["error"],
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        # Generate workspace path
        repo_id = self._generate_repo_id(repo_url, commit_hash)
        repo_path = Path(self._workspace_dir) / repo_id

        try:
            # Clone repository
            clone_result = await self._clone_repo(
                repo_url=repo_url,
                target_path=str(repo_path),
                branch=branch,
            )

            if not clone_result["success"]:
                return CloneResult(
                    passed=False,
                    message=f"Clone failed: {clone_result['error']}",
                    error=clone_result["error"],
                    repo_url=repo_url,
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            # Checkout specific commit if requested
            if commit_hash:
                checkout_result = await self._checkout_commit(
                    repo_path=str(repo_path),
                    commit_hash=commit_hash,
                )
                if not checkout_result["success"]:
                    return CloneResult(
                        passed=False,
                        message=f"Checkout failed: {checkout_result['error']}",
                        error=checkout_result["error"],
                        repo_url=repo_url,
                        started_at=started_at,
                        completed_at=datetime.utcnow(),
                    )
                actual_commit = commit_hash
            else:
                actual_commit = clone_result["commit_hash"]

            # Get repository info
            repo_info = await self._get_repo_info(str(repo_path))

            # Verify repository size
            if repo_info["size_mb"] > settings.max_repo_size_mb:
                return CloneResult(
                    passed=False,
                    message=f"Repository too large: {repo_info['size_mb']:.1f}MB > {settings.max_repo_size_mb}MB",
                    error="repo_too_large",
                    repo_url=repo_url,
                    commit_hash=actual_commit,
                    repo_size_mb=repo_info["size_mb"],
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            # Initialize submodules if present
            if repo_info["has_submodules"]:
                await self._init_submodules(str(repo_path))

            logger.info(
                "repo_cloned_successfully",
                repo_url=repo_url,
                commit=actual_commit,
                size_mb=repo_info["size_mb"],
            )

            return CloneResult(
                passed=True,
                message="Repository cloned and verified successfully",
                repo_url=repo_url,
                commit_hash=actual_commit,
                branch=branch or repo_info.get("default_branch", "main"),
                repo_size_mb=repo_info["size_mb"],
                files_count=repo_info["files_count"],
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.exception("repo_clone_error", repo_url=repo_url, error=str(e))
            return CloneResult(
                passed=False,
                message=f"Clone error: {str(e)}",
                error=str(e),
                repo_url=repo_url,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    def _validate_url(self, url: str) -> dict[str, Any]:
        """Validate git repository URL."""
        try:
            parsed = urlparse(url)

            # Check scheme
            if parsed.scheme not in ("https", "git", "ssh"):
                return {"valid": False, "error": f"Invalid scheme: {parsed.scheme}"}

            # Check host against whitelist
            host = parsed.netloc.split("@")[-1].split(":")[0]
            if host not in settings.allowed_git_hosts:
                return {"valid": False, "error": f"Host not allowed: {host}"}

            # Basic path validation
            if not parsed.path or parsed.path == "/":
                return {"valid": False, "error": "Invalid repository path"}

            # Check for suspicious patterns
            suspicious_patterns = [
                r"\.\./",  # Path traversal
                r";",  # Command injection
                r"\|",  # Pipe
                r"`",  # Backtick
                r"\$\(",  # Command substitution
            ]
            for pattern in suspicious_patterns:
                if re.search(pattern, url):
                    return {"valid": False, "error": "Suspicious URL pattern detected"}

            return {"valid": True, "host": host, "path": parsed.path}

        except Exception as e:
            return {"valid": False, "error": str(e)}

    def _generate_repo_id(self, url: str, commit_hash: str | None) -> str:
        """Generate unique repository ID."""
        key = f"{url}:{commit_hash or 'latest'}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    async def _clone_repo(
        self,
        repo_url: str,
        target_path: str,
        branch: str | None = None,
    ) -> dict[str, Any]:
        """Clone repository with timeout."""
        # Remove existing directory if present
        if os.path.exists(target_path):
            shutil.rmtree(target_path)

        cmd = ["git", "clone", "--depth", "1"]
        if branch:
            cmd.extend(["--branch", branch])
        cmd.extend([repo_url, target_path])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=settings.git_clone_timeout_seconds,
            )

            if process.returncode != 0:
                return {
                    "success": False,
                    "error": stderr.decode("utf-8").strip(),
                }

            # Get current commit
            commit_cmd = ["git", "-C", target_path, "rev-parse", "HEAD"]
            commit_process = await asyncio.create_subprocess_exec(
                *commit_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            commit_stdout, _ = await commit_process.communicate()
            commit_hash = commit_stdout.decode("utf-8").strip()

            return {
                "success": True,
                "commit_hash": commit_hash,
                "output": stdout.decode("utf-8"),
            }

        except asyncio.TimeoutError:
            return {"success": False, "error": "Clone timed out"}

    async def _checkout_commit(
        self,
        repo_path: str,
        commit_hash: str,
    ) -> dict[str, Any]:
        """Checkout specific commit."""
        # First fetch the full history for the commit
        fetch_cmd = ["git", "-C", repo_path, "fetch", "--depth", "1", "origin", commit_hash]
        fetch_process = await asyncio.create_subprocess_exec(
            *fetch_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await fetch_process.communicate()

        # Checkout the commit
        checkout_cmd = ["git", "-C", repo_path, "checkout", commit_hash]
        process = await asyncio.create_subprocess_exec(
            *checkout_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            return {"success": False, "error": stderr.decode("utf-8").strip()}

        return {"success": True}

    async def _get_repo_info(self, repo_path: str) -> dict[str, Any]:
        """Get repository information."""
        path = Path(repo_path)

        # Calculate size
        total_size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        size_mb = total_size / (1024 * 1024)

        # Count files
        files_count = sum(1 for f in path.rglob("*") if f.is_file())

        # Check for submodules
        has_submodules = (path / ".gitmodules").exists()

        # Get default branch
        branch_cmd = ["git", "-C", repo_path, "rev-parse", "--abbrev-ref", "HEAD"]
        process = await asyncio.create_subprocess_exec(
            *branch_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        default_branch = stdout.decode("utf-8").strip()

        return {
            "size_mb": size_mb,
            "files_count": files_count,
            "has_submodules": has_submodules,
            "default_branch": default_branch,
        }

    async def _init_submodules(self, repo_path: str) -> None:
        """Initialize git submodules."""
        cmd = ["git", "-C", repo_path, "submodule", "update", "--init", "--recursive", "--depth", "1"]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.wait_for(
            process.communicate(),
            timeout=settings.git_clone_timeout_seconds,
        )

    async def cleanup(self, repo_id: str) -> None:
        """Clean up cloned repository."""
        repo_path = Path(self._workspace_dir) / repo_id
        if repo_path.exists():
            shutil.rmtree(repo_path)
            logger.info("repo_cleaned_up", repo_id=repo_id)

    def get_repo_path(self, repo_url: str, commit_hash: str | None = None) -> str:
        """Get the filesystem path for a repository."""
        repo_id = self._generate_repo_id(repo_url, commit_hash)
        return str(Path(self._workspace_dir) / repo_id)


class CodeIntegrityChecker:
    """Verifies code integrity and detects potential issues."""

    # Patterns that might indicate problematic code
    SUSPICIOUS_PATTERNS = [
        (r"os\.system\s*\(", "shell_command"),
        (r"subprocess\.(call|run|Popen)", "subprocess_call"),
        (r"eval\s*\(", "eval_usage"),
        (r"exec\s*\(", "exec_usage"),
        (r"__import__\s*\(", "dynamic_import"),
        (r"pickle\.load", "pickle_load"),
        (r"torch\.load.*weights_only\s*=\s*False", "unsafe_torch_load"),
    ]

    async def check_integrity(
        self,
        repo_path: str,
        patterns_to_check: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Check code integrity for potential issues.

        Args:
            repo_path: Path to repository
            patterns_to_check: Optional list of file patterns to check

        Returns:
            Dictionary with integrity check results
        """
        patterns = patterns_to_check or ["**/*.py"]
        issues = []

        path = Path(repo_path)
        for pattern in patterns:
            for file_path in path.glob(pattern):
                if file_path.is_file():
                    file_issues = await self._check_file(file_path)
                    if file_issues:
                        issues.extend(file_issues)

        return {
            "passed": len(issues) == 0,
            "issues_count": len(issues),
            "issues": issues[:50],  # Limit to first 50
        }

    async def _check_file(self, file_path: Path) -> list[dict[str, Any]]:
        """Check a single file for issues."""
        issues = []

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")

            for pattern, issue_type in self.SUSPICIOUS_PATTERNS:
                matches = list(re.finditer(pattern, content))
                for match in matches:
                    line_num = content[:match.start()].count("\n") + 1
                    issues.append({
                        "file": str(file_path),
                        "line": line_num,
                        "type": issue_type,
                        "snippet": content[max(0, match.start() - 20):match.end() + 20],
                    })

        except Exception as e:
            issues.append({
                "file": str(file_path),
                "type": "read_error",
                "error": str(e),
            })

        return issues


class RequirementsExtractor:
    """Extracts dependencies from ML repositories."""

    async def extract_requirements(
        self,
        repo_path: str,
    ) -> dict[str, Any]:
        """
        Extract all dependencies from a repository.

        Args:
            repo_path: Path to repository

        Returns:
            Dictionary with extracted dependencies
        """
        path = Path(repo_path)
        requirements = {
            "pip": [],
            "conda": [],
            "system": [],
            "docker": None,
            "nix": None,
        }

        # Check requirements.txt
        req_txt = path / "requirements.txt"
        if req_txt.exists():
            requirements["pip"].extend(self._parse_requirements_txt(req_txt))

        # Check setup.py
        setup_py = path / "setup.py"
        if setup_py.exists():
            requirements["pip"].extend(await self._parse_setup_py(setup_py))

        # Check pyproject.toml
        pyproject = path / "pyproject.toml"
        if pyproject.exists():
            requirements["pip"].extend(await self._parse_pyproject(pyproject))

        # Check environment.yml (conda)
        env_yml = path / "environment.yml"
        if env_yml.exists():
            requirements["conda"] = await self._parse_conda_env(env_yml)

        # Check Dockerfile
        dockerfile = path / "Dockerfile"
        if dockerfile.exists():
            requirements["docker"] = dockerfile.read_text()

        # Check flake.nix
        flake_nix = path / "flake.nix"
        if flake_nix.exists():
            requirements["nix"] = flake_nix.read_text()

        return requirements

    def _parse_requirements_txt(self, path: Path) -> list[str]:
        """Parse requirements.txt file."""
        requirements = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("-"):
                requirements.append(line)
        return requirements

    async def _parse_setup_py(self, path: Path) -> list[str]:
        """Parse setup.py for dependencies."""
        # Simple regex-based extraction
        content = path.read_text()
        install_requires = re.search(
            r"install_requires\s*=\s*\[(.*?)\]",
            content,
            re.DOTALL,
        )
        if install_requires:
            deps = re.findall(r"['\"]([^'\"]+)['\"]", install_requires.group(1))
            return deps
        return []

    async def _parse_pyproject(self, path: Path) -> list[str]:
        """Parse pyproject.toml for dependencies."""
        try:
            import tomllib

            content = path.read_bytes()
            data = tomllib.loads(content.decode("utf-8"))

            deps = []
            # PEP 621 dependencies
            if "project" in data and "dependencies" in data["project"]:
                deps.extend(data["project"]["dependencies"])

            # Poetry dependencies
            if "tool" in data and "poetry" in data["tool"]:
                poetry_deps = data["tool"]["poetry"].get("dependencies", {})
                for name, spec in poetry_deps.items():
                    if name != "python":
                        if isinstance(spec, str):
                            deps.append(f"{name}{spec}" if spec != "*" else name)
                        else:
                            deps.append(name)

            return deps
        except Exception:
            return []

    async def _parse_conda_env(self, path: Path) -> list[str]:
        """Parse conda environment.yml."""
        try:
            import yaml

            data = yaml.safe_load(path.read_text())
            return data.get("dependencies", [])
        except Exception:
            return []

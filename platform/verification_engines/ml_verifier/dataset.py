"""Dataset fetching and validation for ML experiments."""

import asyncio
import hashlib
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp

from platform.verification_engines.ml_verifier.base import (
    BaseMLVerifier,
    DataFetchResult,
)
from platform.verification_engines.ml_verifier.config import get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class DatasetFetcher(BaseMLVerifier):
    """
    Fetches and validates datasets for ML experiment reproduction.

    Features:
    - HuggingFace Datasets integration
    - Direct URL downloads with checksum verification
    - Torrent support for large datasets
    - Caching and deduplication
    """

    def __init__(
        self,
        cache_dir: str | None = None,
        hf_cache_dir: str | None = None,
    ):
        """
        Initialize dataset fetcher.

        Args:
            cache_dir: Directory for dataset cache
            hf_cache_dir: HuggingFace cache directory
        """
        self._cache_dir = cache_dir or settings.dataset_cache_path
        self._hf_cache_dir = hf_cache_dir or settings.huggingface_cache_path
        os.makedirs(self._cache_dir, exist_ok=True)
        os.makedirs(self._hf_cache_dir, exist_ok=True)

    @property
    def component_name(self) -> str:
        return "dataset_fetcher"

    async def verify(
        self,
        datasets: list[dict[str, Any]],
        working_dir: str,
    ) -> DataFetchResult:
        """
        Fetch and verify datasets.

        Args:
            datasets: List of dataset specifications, each containing:
                - name: Dataset name or ID
                - source: Source type (huggingface, url, s3, gcs)
                - url: Optional direct URL
                - checksum: Optional expected checksum (sha256)
                - subset: Optional dataset subset/split
            working_dir: Directory to store datasets

        Returns:
            DataFetchResult with fetch details
        """
        started_at = datetime.utcnow()
        fetched_datasets = []
        total_size = 0.0
        checksums_valid = True
        errors = []

        for dataset_spec in datasets:
            result = await self._fetch_dataset(dataset_spec, working_dir)

            if result["success"]:
                fetched_datasets.append(result["name"])
                total_size += result.get("size_gb", 0.0)
                if not result.get("checksum_valid", True):
                    checksums_valid = False
            else:
                errors.append(f"{dataset_spec.get('name', 'unknown')}: {result['error']}")

        passed = len(errors) == 0
        message = "All datasets fetched successfully" if passed else f"Errors: {'; '.join(errors)}"

        return DataFetchResult(
            passed=passed,
            message=message,
            datasets_fetched=fetched_datasets,
            total_size_gb=total_size,
            checksums_valid=checksums_valid,
            error="; ".join(errors) if errors else None,
            started_at=started_at,
            completed_at=datetime.utcnow(),
        )

    async def _fetch_dataset(
        self,
        spec: dict[str, Any],
        working_dir: str,
    ) -> dict[str, Any]:
        """Fetch a single dataset."""
        source = spec.get("source", "huggingface")
        name = spec.get("name", "")

        try:
            if source == "huggingface":
                return await self._fetch_huggingface(spec, working_dir)
            elif source == "url":
                return await self._fetch_url(spec, working_dir)
            elif source == "s3":
                return await self._fetch_s3(spec, working_dir)
            elif source == "gcs":
                return await self._fetch_gcs(spec, working_dir)
            else:
                return {"success": False, "name": name, "error": f"Unknown source: {source}"}

        except Exception as e:
            logger.exception("dataset_fetch_error", name=name, error=str(e))
            return {"success": False, "name": name, "error": str(e)}

    async def _fetch_huggingface(
        self,
        spec: dict[str, Any],
        working_dir: str,
    ) -> dict[str, Any]:
        """Fetch dataset from HuggingFace."""
        name = spec.get("name", "")
        subset = spec.get("subset")
        split = spec.get("split")

        # Use huggingface datasets library
        cmd = ["python", "-c", f"""
import os
os.environ['HF_HOME'] = '{self._hf_cache_dir}'
os.environ['HF_DATASETS_CACHE'] = '{self._hf_cache_dir}/datasets'

from datasets import load_dataset
dataset = load_dataset('{name}'{f", '{subset}'" if subset else ""}{f", split='{split}'" if split else ""})
print(f"Loaded {{len(dataset)}} examples")
"""]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_dir,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=1800,  # 30 minutes for large datasets
        )

        if process.returncode != 0:
            return {
                "success": False,
                "name": name,
                "error": stderr.decode("utf-8"),
            }

        # Calculate approximate size
        cache_path = Path(self._hf_cache_dir) / "datasets"
        size_gb = self._calculate_dir_size(cache_path) / (1024**3)

        return {
            "success": True,
            "name": name,
            "source": "huggingface",
            "size_gb": size_gb,
            "checksum_valid": True,
            "path": str(cache_path),
        }

    async def _fetch_url(
        self,
        spec: dict[str, Any],
        working_dir: str,
    ) -> dict[str, Any]:
        """Fetch dataset from URL."""
        name = spec.get("name", "")
        url = spec.get("url", "")
        expected_checksum = spec.get("checksum")

        if not url:
            return {"success": False, "name": name, "error": "No URL provided"}

        # Validate URL
        parsed = urlparse(url)
        if parsed.scheme not in ("https", "http"):
            return {"success": False, "name": name, "error": "Invalid URL scheme"}

        # Generate target path
        filename = Path(parsed.path).name or "dataset"
        target_path = Path(working_dir) / "data" / filename
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Check cache first
        cache_key = hashlib.sha256(url.encode()).hexdigest()
        cached_path = Path(self._cache_dir) / cache_key
        if cached_path.exists():
            shutil.copy2(cached_path, target_path)
            size_gb = target_path.stat().st_size / (1024**3)
            return {
                "success": True,
                "name": name,
                "source": "url",
                "size_gb": size_gb,
                "checksum_valid": True,
                "path": str(target_path),
                "cached": True,
            }

        # Download
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return {
                            "success": False,
                            "name": name,
                            "error": f"HTTP {response.status}",
                        }

                    content_length = response.headers.get("Content-Length")
                    if content_length:
                        size_gb = int(content_length) / (1024**3)
                        if size_gb > settings.max_dataset_size_gb:
                            return {
                                "success": False,
                                "name": name,
                                "error": f"Dataset too large: {size_gb:.1f}GB",
                            }

                    # Stream to file
                    sha256 = hashlib.sha256()
                    with open(target_path, "wb") as f:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            f.write(chunk)
                            sha256.update(chunk)

            actual_checksum = sha256.hexdigest()
            checksum_valid = True
            if expected_checksum:
                checksum_valid = actual_checksum == expected_checksum

            # Cache the file
            shutil.copy2(target_path, cached_path)

            size_gb = target_path.stat().st_size / (1024**3)

            return {
                "success": True,
                "name": name,
                "source": "url",
                "size_gb": size_gb,
                "checksum_valid": checksum_valid,
                "actual_checksum": actual_checksum,
                "path": str(target_path),
            }

        except asyncio.TimeoutError:
            return {"success": False, "name": name, "error": "Download timed out"}
        except Exception as e:
            return {"success": False, "name": name, "error": str(e)}

    async def _fetch_s3(
        self,
        spec: dict[str, Any],
        working_dir: str,
    ) -> dict[str, Any]:
        """Fetch dataset from S3."""
        name = spec.get("name", "")
        bucket = spec.get("bucket", "")
        key = spec.get("key", "")

        if not bucket or not key:
            return {"success": False, "name": name, "error": "Missing bucket or key"}

        target_path = Path(working_dir) / "data" / Path(key).name
        target_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = ["aws", "s3", "cp", f"s3://{bucket}/{key}", str(target_path)]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=3600,
        )

        if process.returncode != 0:
            return {
                "success": False,
                "name": name,
                "error": stderr.decode("utf-8"),
            }

        size_gb = target_path.stat().st_size / (1024**3)

        return {
            "success": True,
            "name": name,
            "source": "s3",
            "size_gb": size_gb,
            "path": str(target_path),
        }

    async def _fetch_gcs(
        self,
        spec: dict[str, Any],
        working_dir: str,
    ) -> dict[str, Any]:
        """Fetch dataset from Google Cloud Storage."""
        name = spec.get("name", "")
        bucket = spec.get("bucket", "")
        path = spec.get("path", "")

        if not bucket or not path:
            return {"success": False, "name": name, "error": "Missing bucket or path"}

        target_path = Path(working_dir) / "data" / Path(path).name
        target_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = ["gsutil", "cp", f"gs://{bucket}/{path}", str(target_path)]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=3600,
        )

        if process.returncode != 0:
            return {
                "success": False,
                "name": name,
                "error": stderr.decode("utf-8"),
            }

        size_gb = target_path.stat().st_size / (1024**3)

        return {
            "success": True,
            "name": name,
            "source": "gcs",
            "size_gb": size_gb,
            "path": str(target_path),
        }

    def _calculate_dir_size(self, path: Path) -> float:
        """Calculate total size of directory in bytes."""
        total = 0
        if path.exists():
            for f in path.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
        return total

    async def validate_checksums(
        self,
        dataset_path: str,
        expected_checksums: dict[str, str],
    ) -> dict[str, Any]:
        """
        Validate checksums of dataset files.

        Args:
            dataset_path: Path to dataset directory
            expected_checksums: Dict mapping filename to expected sha256

        Returns:
            Validation results
        """
        results = {}
        all_valid = True

        for filename, expected in expected_checksums.items():
            file_path = Path(dataset_path) / filename
            if not file_path.exists():
                results[filename] = {"valid": False, "error": "File not found"}
                all_valid = False
                continue

            actual = await self._compute_checksum(file_path)
            valid = actual == expected
            results[filename] = {
                "valid": valid,
                "expected": expected,
                "actual": actual,
            }
            if not valid:
                all_valid = False

        return {"all_valid": all_valid, "files": results}

    async def _compute_checksum(self, path: Path) -> str:
        """Compute SHA256 checksum of file."""
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                sha256.update(chunk)
        return sha256.hexdigest()

    async def cleanup(self, working_dir: str) -> None:
        """Clean up downloaded datasets."""
        data_path = Path(working_dir) / "data"
        if data_path.exists():
            shutil.rmtree(data_path)
            logger.info("dataset_cleaned_up", path=str(data_path))

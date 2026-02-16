"""Cross-cutting verifier: Data Integrity Checks.

Validates data quality via schema validation, duplicate detection,
outlier flagging, and hash verification.
"""
from __future__ import annotations

import asyncio
import hashlib
import math
import time
from typing import Any

from backend.logging_config import get_logger
from backend.verification.cross_cutting_base import (
    CrossCuttingResult,
    CrossCuttingVerifier,
)

logger = get_logger(__name__)


class DataIntegrityVerifier(CrossCuttingVerifier):
    name = "data_integrity"
    default_weight = 0.10

    def is_applicable(self, task_result: dict, task_metadata: dict) -> bool:
        data_keys = {"data", "dataset", "raw_data", "results_summary", "output_checksums"}
        return any(k in task_result and task_result[k] for k in data_keys)

    async def verify(self, task_result: dict, task_metadata: dict) -> CrossCuttingResult:
        start = time.monotonic()

        component_scores: dict[str, float] = {}
        details: dict[str, Any] = {}
        warnings: list[str] = []

        data = self._extract_data(task_result)
        checksums = task_result.get("output_checksums", {})
        schema_def = task_result.get("schema") or task_result.get("expected_schema")

        # Run all checks concurrently via threads
        schema_task = asyncio.to_thread(self._check_schema, data, schema_def) if data else _neutral("No data for schema check")
        dup_task = asyncio.to_thread(self._check_duplicates, data) if data else _neutral("No data for duplicate check")
        outlier_task = asyncio.to_thread(self._check_outliers, data) if data else _neutral("No data for outlier check")
        hash_task = asyncio.to_thread(self._check_hashes, task_result, checksums) if checksums else _neutral("No checksums")

        schema_result, dup_result, outlier_result, hash_result = await asyncio.gather(
            schema_task, dup_task, outlier_task, hash_task,
        )

        for name, result in [("schema_valid", schema_result), ("no_duplicates", dup_result),
                             ("no_outliers", outlier_result), ("hash_match", hash_result)]:
            component_scores[name] = result.get("score", 0.5)
            details[name] = result
            if result.get("warnings"):
                warnings.extend(result["warnings"])

        # Equal weights for all 4 components
        applicable = [k for k in component_scores if details[k].get("applicable", True)]
        if applicable:
            score = sum(component_scores[k] for k in applicable) / len(applicable)
        else:
            score = 0.5

        elapsed = time.monotonic() - start
        details["component_scores"] = component_scores

        return CrossCuttingResult(
            verifier_name=self.name,
            score=round(score, 4),
            weight=self.default_weight,
            details=details,
            warnings=warnings,
            compute_time_seconds=elapsed,
        )

    @staticmethod
    def _extract_data(task_result: dict) -> list[dict] | None:
        """Extract tabular data from task result."""
        for key in ("data", "dataset", "raw_data"):
            raw = task_result.get(key)
            if isinstance(raw, list) and raw and isinstance(raw[0], dict):
                return raw
            if isinstance(raw, dict):
                # Single-row or nested data — try to extract rows
                if "rows" in raw and isinstance(raw["rows"], list):
                    return raw["rows"]
                if "records" in raw and isinstance(raw["records"], list):
                    return raw["records"]

        # results_summary may contain numeric data
        summary = task_result.get("results_summary")
        if isinstance(summary, dict):
            # Convert summary to single-row dataset for outlier check
            numeric_vals = {k: v for k, v in summary.items() if isinstance(v, (int, float))}
            if numeric_vals:
                return [numeric_vals]

        return None

    @staticmethod
    def _check_schema(data: list[dict], schema_def: dict | None) -> dict:
        """Validate data structure against declared schema."""
        if not data:
            return {"score": 0.5, "applicable": False, "note": "No data"}

        # If explicit schema is provided, validate against it
        if schema_def and isinstance(schema_def, dict):
            expected_fields = set(schema_def.get("fields", schema_def.get("columns", [])))
            if expected_fields:
                actual_fields = set(data[0].keys()) if data else set()
                missing = expected_fields - actual_fields
                extra = actual_fields - expected_fields
                coverage = len(expected_fields - missing) / len(expected_fields) if expected_fields else 0
                return {
                    "score": round(coverage, 4),
                    "applicable": True,
                    "expected_fields": sorted(expected_fields),
                    "missing_fields": sorted(missing),
                    "extra_fields": sorted(extra),
                }

        # Basic structural consistency check: all rows have same keys
        if len(data) < 2:
            return {"score": 1.0, "applicable": True, "note": "Single row, schema consistent"}

        ref_keys = set(data[0].keys())
        inconsistent = 0
        for i, row in enumerate(data[1:], 1):
            if set(row.keys()) != ref_keys:
                inconsistent += 1
                if inconsistent >= 5:
                    break

        score = 1.0 - (inconsistent / min(len(data) - 1, 100))
        return {
            "score": round(max(0.0, score), 4),
            "applicable": True,
            "total_rows": len(data),
            "inconsistent_rows": inconsistent,
            "columns": sorted(ref_keys),
        }

    @staticmethod
    def _check_duplicates(data: list[dict]) -> dict:
        """Detect exact and near-duplicate rows."""
        if not data or len(data) < 2:
            return {"score": 1.0, "applicable": True, "duplicates": 0}

        seen: set[str] = set()
        exact_dupes = 0

        for row in data:
            key = str(sorted(row.items()))
            if key in seen:
                exact_dupes += 1
            else:
                seen.add(key)

        dup_ratio = exact_dupes / len(data) if data else 0

        if dup_ratio > 0.5:
            score = 0.1
        elif dup_ratio > 0.2:
            score = 0.4
        elif dup_ratio > 0.05:
            score = 0.7
        else:
            score = 1.0

        return {
            "score": round(score, 4),
            "applicable": True,
            "total_rows": len(data),
            "exact_duplicates": exact_dupes,
            "duplicate_ratio": round(dup_ratio, 4),
            "warnings": [f"{exact_dupes} exact duplicate rows detected"] if exact_dupes > 0 else [],
        }

    @staticmethod
    def _check_outliers(data: list[dict]) -> dict:
        """Detect anomalous outliers via z-score (>3 sigma)."""
        if not data:
            return {"score": 0.5, "applicable": False, "note": "No data"}

        # Collect numeric columns
        numeric_cols: dict[str, list[float]] = {}
        for row in data:
            for k, v in row.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
                    numeric_cols.setdefault(k, []).append(float(v))

        if not numeric_cols:
            return {"score": 0.5, "applicable": False, "note": "No numeric columns"}

        outlier_counts: dict[str, int] = {}
        total_values = 0
        total_outliers = 0

        for col, values in numeric_cols.items():
            if len(values) < 5:
                continue

            total_values += len(values)
            mean = sum(values) / len(values)
            variance = sum((x - mean) ** 2 for x in values) / len(values)
            std = math.sqrt(variance) if variance > 0 else 0

            if std == 0:
                continue

            n_outliers = sum(1 for x in values if abs((x - mean) / std) > 3.0)
            if n_outliers > 0:
                outlier_counts[col] = n_outliers
                total_outliers += n_outliers

        if total_values == 0:
            return {"score": 0.5, "applicable": False, "note": "Insufficient numeric data"}

        outlier_ratio = total_outliers / total_values
        # Expect ~0.3% outliers under normal distribution
        if outlier_ratio > 0.10:
            score = 0.2
        elif outlier_ratio > 0.05:
            score = 0.5
        elif outlier_ratio > 0.01:
            score = 0.8
        else:
            score = 1.0

        return {
            "score": round(score, 4),
            "applicable": True,
            "columns_checked": len(numeric_cols),
            "total_values": total_values,
            "total_outliers": total_outliers,
            "outlier_ratio": round(outlier_ratio, 6),
            "outlier_columns": outlier_counts,
            "warnings": [f"High outlier ratio ({outlier_ratio:.1%}) in columns: {list(outlier_counts.keys())}"]
                        if outlier_ratio > 0.05 else [],
        }

    @staticmethod
    def _check_hashes(task_result: dict, checksums: dict) -> dict:
        """Verify SHA-256 hashes of data blobs."""
        if not checksums:
            return {"score": 0.5, "applicable": False, "note": "No checksums"}

        matches = 0
        mismatches = 0
        checks: list[dict] = []

        for key, expected_hash in checksums.items():
            data_blob = task_result.get(key)
            if data_blob is None:
                # Try nested data
                for container_key in ("data", "raw_data", "dataset"):
                    container = task_result.get(container_key)
                    if isinstance(container, dict) and key in container:
                        data_blob = container[key]
                        break

            if data_blob is None:
                checks.append({"key": key, "match": False, "note": "Data not found"})
                mismatches += 1
                continue

            if isinstance(data_blob, (dict, list)):
                serialised = _canonical_json(data_blob)
            else:
                serialised = str(data_blob)

            actual_hash = hashlib.sha256(serialised.encode()).hexdigest()
            match = actual_hash == expected_hash
            checks.append({
                "key": key,
                "match": match,
                "expected": expected_hash[:16] + "...",
                "actual": actual_hash[:16] + "...",
            })

            if match:
                matches += 1
            else:
                mismatches += 1

        total = matches + mismatches
        score = matches / total if total > 0 else 0.5

        return {
            "score": round(score, 4),
            "applicable": True,
            "matches": matches,
            "mismatches": mismatches,
            "checks": checks,
            "warnings": [f"{mismatches} hash mismatch(es)"] if mismatches > 0 else [],
        }


def _canonical_json(obj: Any) -> str:
    """Produce a canonical JSON string for hashing."""
    import json
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


async def _neutral(note: str) -> dict:
    return {"score": 0.5, "applicable": False, "note": note}

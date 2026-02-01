"""Kubernetes job runner for ML experiment execution."""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any

from platform.verification_engines.ml_verifier.base import (
    BaseJobRunner,
    ExecutionResult,
    ResourceUsage,
)
from platform.verification_engines.ml_verifier.config import GPU_CONFIGS, get_settings
from platform.shared.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class KubernetesJobRunner(BaseJobRunner):
    """
    Runs ML experiments as Kubernetes Jobs.

    Features:
    - GPU scheduling and resource management
    - Pod affinity for optimal placement
    - Log streaming and artifact collection
    - Timeout handling and cleanup
    """

    def __init__(
        self,
        namespace: str | None = None,
        service_account: str | None = None,
    ):
        """
        Initialize Kubernetes job runner.

        Args:
            namespace: Kubernetes namespace
            service_account: Service account for jobs
        """
        self._namespace = namespace or settings.k8s_namespace
        self._service_account = service_account or settings.k8s_service_account

    @property
    def runner_name(self) -> str:
        return "kubernetes"

    async def submit_job(
        self,
        job_spec: dict[str, Any],
        timeout_seconds: int,
    ) -> str:
        """
        Submit a job to Kubernetes.

        Args:
            job_spec: Job specification containing:
                - image: Container image to run
                - command: Command to execute
                - args: Command arguments
                - env: Environment variables
                - gpu_type: GPU type (a100_40gb, etc.)
                - gpu_count: Number of GPUs
                - memory_gb: Memory limit
                - cpu_cores: CPU cores
            timeout_seconds: Job timeout

        Returns:
            Job ID
        """
        job_id = f"ml-verify-{uuid.uuid4().hex[:12]}"

        # Build Kubernetes Job manifest
        manifest = self._build_job_manifest(
            job_id=job_id,
            job_spec=job_spec,
            timeout_seconds=timeout_seconds,
        )

        # Apply the job
        cmd = ["kubectl", "apply", "-n", self._namespace, "-f", "-"]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate(
            input=json.dumps(manifest).encode()
        )

        if process.returncode != 0:
            raise RuntimeError(f"Failed to submit job: {stderr.decode()}")

        logger.info("k8s_job_submitted", job_id=job_id, namespace=self._namespace)
        return job_id

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Get status of a Kubernetes job."""
        cmd = [
            "kubectl", "get", "job", job_id,
            "-n", self._namespace,
            "-o", "json",
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            return {"status": "unknown", "error": stderr.decode()}

        job_data = json.loads(stdout.decode())
        status = job_data.get("status", {})

        # Determine job state
        if status.get("succeeded", 0) > 0:
            state = "completed"
        elif status.get("failed", 0) > 0:
            state = "failed"
        elif status.get("active", 0) > 0:
            state = "running"
        else:
            state = "pending"

        return {
            "status": state,
            "active": status.get("active", 0),
            "succeeded": status.get("succeeded", 0),
            "failed": status.get("failed", 0),
            "start_time": status.get("startTime"),
            "completion_time": status.get("completionTime"),
        }

    async def get_job_logs(self, job_id: str) -> str:
        """Get logs from a Kubernetes job."""
        # Get pod name for the job
        cmd = [
            "kubectl", "get", "pods",
            "-n", self._namespace,
            "-l", f"job-name={job_id}",
            "-o", "jsonpath={.items[0].metadata.name}",
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, _ = await process.communicate()
        pod_name = stdout.decode().strip()

        if not pod_name:
            return "No pod found for job"

        # Get logs
        log_cmd = [
            "kubectl", "logs", pod_name,
            "-n", self._namespace,
            "--tail", "10000",
        ]

        log_process = await asyncio.create_subprocess_exec(
            *log_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        log_stdout, _ = await log_process.communicate()
        return log_stdout.decode()

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running Kubernetes job."""
        cmd = [
            "kubectl", "delete", "job", job_id,
            "-n", self._namespace,
            "--grace-period=30",
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await process.communicate()

        if process.returncode != 0:
            logger.warning("k8s_job_cancel_failed", job_id=job_id, error=stderr.decode())
            return False

        logger.info("k8s_job_cancelled", job_id=job_id)
        return True

    async def wait_for_completion(
        self,
        job_id: str,
        timeout_seconds: int,
    ) -> ExecutionResult:
        """Wait for job completion and return result."""
        started_at = datetime.utcnow()
        poll_interval = 10  # seconds

        while True:
            elapsed = (datetime.utcnow() - started_at).total_seconds()
            if elapsed > timeout_seconds:
                await self.cancel_job(job_id)
                return ExecutionResult(
                    passed=False,
                    message="Job timed out",
                    error="timeout",
                    runtime_seconds=elapsed,
                    exit_code=-1,
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            status = await self.get_job_status(job_id)
            state = status.get("status")

            if state == "completed":
                logs = await self.get_job_logs(job_id)
                metrics = await self._get_resource_metrics(job_id)

                return ExecutionResult(
                    passed=True,
                    message="Job completed successfully",
                    runtime_seconds=elapsed,
                    exit_code=0,
                    stdout_tail=logs[-5000:] if logs else "",
                    gpu_hours=metrics.gpu_hours,
                    peak_memory_gb=metrics.peak_memory_gb,
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            elif state == "failed":
                logs = await self.get_job_logs(job_id)
                return ExecutionResult(
                    passed=False,
                    message="Job failed",
                    error="job_failed",
                    runtime_seconds=elapsed,
                    exit_code=1,
                    stderr_tail=logs[-5000:] if logs else "",
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                )

            await asyncio.sleep(poll_interval)

    def _build_job_manifest(
        self,
        job_id: str,
        job_spec: dict[str, Any],
        timeout_seconds: int,
    ) -> dict[str, Any]:
        """Build Kubernetes Job manifest."""
        gpu_type = job_spec.get("gpu_type", "a100_40gb")
        gpu_count = job_spec.get("gpu_count", 1)
        memory_gb = job_spec.get("memory_gb", 32)
        cpu_cores = job_spec.get("cpu_cores", 8)

        gpu_config = GPU_CONFIGS.get(gpu_type, GPU_CONFIGS["a100_40gb"])

        # Build container spec
        container = {
            "name": "ml-experiment",
            "image": job_spec.get("image"),
            "command": job_spec.get("command", ["/bin/bash"]),
            "args": job_spec.get("args", ["-c", "python main.py"]),
            "env": [
                {"name": k, "value": str(v)}
                for k, v in job_spec.get("env", {}).items()
            ],
            "resources": {
                "requests": {
                    "cpu": str(cpu_cores),
                    "memory": f"{memory_gb}Gi",
                    "nvidia.com/gpu": str(gpu_count),
                },
                "limits": {
                    "cpu": str(cpu_cores * 2),
                    "memory": f"{memory_gb * 2}Gi",
                    "nvidia.com/gpu": str(gpu_count),
                },
            },
            "volumeMounts": [
                {"name": "workspace", "mountPath": "/workspace"},
                {"name": "data", "mountPath": "/data"},
                {"name": "output", "mountPath": "/output"},
            ],
        }

        # Build job manifest
        manifest = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_id,
                "namespace": self._namespace,
                "labels": {
                    "app": "ml-verification",
                    "job-id": job_id,
                },
            },
            "spec": {
                "backoffLimit": 0,  # No retries
                "activeDeadlineSeconds": timeout_seconds,
                "ttlSecondsAfterFinished": 3600,  # Clean up after 1 hour
                "template": {
                    "metadata": {
                        "labels": {
                            "app": "ml-verification",
                            "job-id": job_id,
                        },
                    },
                    "spec": {
                        "restartPolicy": "Never",
                        "serviceAccountName": self._service_account,
                        "nodeSelector": settings.gpu_node_selector,
                        "tolerations": [
                            {
                                "key": "nvidia.com/gpu",
                                "operator": "Exists",
                                "effect": "NoSchedule",
                            },
                        ],
                        "containers": [container],
                        "volumes": [
                            {
                                "name": "workspace",
                                "emptyDir": {},
                            },
                            {
                                "name": "data",
                                "persistentVolumeClaim": {
                                    "claimName": "ml-data-pvc",
                                },
                            },
                            {
                                "name": "output",
                                "emptyDir": {},
                            },
                        ],
                    },
                },
            },
        }

        return manifest

    async def _get_resource_metrics(self, job_id: str) -> ResourceUsage:
        """Get resource usage metrics for a job."""
        # Get pod metrics
        cmd = [
            "kubectl", "top", "pod",
            "-n", self._namespace,
            "-l", f"job-name={job_id}",
            "--no-headers",
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, _ = await process.communicate()

        # Parse metrics (simplified)
        metrics = ResourceUsage()
        output = stdout.decode().strip()
        if output:
            # Example: "pod-name   500m   2Gi"
            parts = output.split()
            if len(parts) >= 3:
                cpu_str = parts[1]
                mem_str = parts[2]

                # Parse CPU (convert millicores to hours)
                if cpu_str.endswith("m"):
                    cpu_millicores = int(cpu_str[:-1])
                    metrics.cpu_hours = cpu_millicores / 1000 / 3600

                # Parse memory
                if mem_str.endswith("Gi"):
                    metrics.peak_memory_gb = float(mem_str[:-2])
                elif mem_str.endswith("Mi"):
                    metrics.peak_memory_gb = float(mem_str[:-2]) / 1024

        return metrics


class LocalJobRunner(BaseJobRunner):
    """
    Runs ML experiments locally using Docker.

    Used for testing and development when Kubernetes is not available.
    """

    @property
    def runner_name(self) -> str:
        return "local_docker"

    async def submit_job(
        self,
        job_spec: dict[str, Any],
        timeout_seconds: int,
    ) -> str:
        """Submit a local Docker job."""
        job_id = f"local-{uuid.uuid4().hex[:12]}"

        # Build docker run command
        image = job_spec.get("image")
        command = job_spec.get("command", [])
        args = job_spec.get("args", [])
        env = job_spec.get("env", {})

        cmd = ["docker", "run", "-d", "--name", job_id]

        # Add environment variables
        for key, value in env.items():
            cmd.extend(["-e", f"{key}={value}"])

        # Add GPU support if available
        cmd.extend(["--gpus", "all"])

        # Add image and command
        cmd.append(image)
        cmd.extend(command)
        cmd.extend(args)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"Failed to start container: {stderr.decode()}")

        return job_id

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Get status of a Docker container."""
        cmd = [
            "docker", "inspect",
            "--format", "{{.State.Status}}",
            job_id,
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, _ = await process.communicate()
        status = stdout.decode().strip()

        state_map = {
            "running": "running",
            "exited": "completed",
            "dead": "failed",
            "created": "pending",
        }

        return {"status": state_map.get(status, "unknown")}

    async def get_job_logs(self, job_id: str) -> str:
        """Get logs from a Docker container."""
        cmd = ["docker", "logs", "--tail", "10000", job_id]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await process.communicate()
        return stdout.decode() + stderr.decode()

    async def cancel_job(self, job_id: str) -> bool:
        """Stop and remove a Docker container."""
        stop_cmd = ["docker", "stop", job_id]
        rm_cmd = ["docker", "rm", job_id]

        for cmd in [stop_cmd, rm_cmd]:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()

        return True

    async def wait_for_completion(
        self,
        job_id: str,
        timeout_seconds: int,
    ) -> ExecutionResult:
        """Wait for container completion."""
        started_at = datetime.utcnow()

        cmd = ["docker", "wait", job_id]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds,
            )

            exit_code = int(stdout.decode().strip())
            logs = await self.get_job_logs(job_id)
            elapsed = (datetime.utcnow() - started_at).total_seconds()

            return ExecutionResult(
                passed=exit_code == 0,
                message="Job completed" if exit_code == 0 else "Job failed",
                runtime_seconds=elapsed,
                exit_code=exit_code,
                stdout_tail=logs[-5000:],
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except asyncio.TimeoutError:
            await self.cancel_job(job_id)
            return ExecutionResult(
                passed=False,
                message="Job timed out",
                error="timeout",
                runtime_seconds=timeout_seconds,
                exit_code=-1,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

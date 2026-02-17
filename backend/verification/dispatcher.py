"""Route verification requests to the correct domain adapter."""
from __future__ import annotations

from backend.verification.base import VerificationAdapter, VerificationResult
from backend.logging_config import get_logger

logger = get_logger(__name__)

# Domains that require Docker containers for verification
DOCKER_DOMAINS: set[str] = {"mathematics", "computational_biology"}


def is_docker_domain(domain: str) -> bool:
    """Return True if verification for this domain runs in a Docker container."""
    return domain in DOCKER_DOMAINS


# Registry — populated at import time
_ADAPTERS: dict[str, VerificationAdapter] = {}


def register_adapter(adapter: VerificationAdapter) -> None:
    _ADAPTERS[adapter.domain] = adapter


def get_adapter(domain: str) -> VerificationAdapter | None:
    return _ADAPTERS.get(domain)


async def dispatch_verification(
    domain: str,
    task_result: dict,
    task_metadata: dict,
) -> VerificationResult:
    adapter = get_adapter(domain)
    if adapter is None:
        logger.warning("no_adapter", domain=domain)
        return VerificationResult.fail(domain, [f"No verification adapter for domain: {domain}"])

    try:
        result = await adapter.verify(task_result, task_metadata)
        logger.info(
            "verification_complete",
            domain=domain,
            passed=result.passed,
            score=result.score,
            badge=result.badge.value,
        )
        return result
    except Exception as e:
        logger.exception("verification_error", domain=domain)
        return VerificationResult.fail(domain, [f"Verification error: {str(e)}"])


# ----- Auto-register on import -----
def _register_all() -> None:
    """Import and register all adapters. Called once at startup."""
    from backend.verification.lean4_adapter import Lean4Adapter
    from backend.verification.ml_repro_adapter import MLReproAdapter
    from backend.verification.compbio_adapter import CompBioAdapter
    from backend.verification.materials_adapter import MaterialsAdapter
    from backend.verification.bioinfo_adapter import BioInfoAdapter
    from backend.verification.chemistry_adapter import ChemistryAdapter
    from backend.verification.physics_adapter import PhysicsAdapter
    from backend.verification.genomics_adapter import GenomicsAdapter
    from backend.verification.epidemiology_adapter import EpidemiologyAdapter
    from backend.verification.systems_biology_adapter import SystemsBiologyAdapter
    from backend.verification.immunoinformatics_adapter import ImmunoinformaticsAdapter
    from backend.verification.metabolomics_adapter import MetabolomicsAdapter

    for cls in [Lean4Adapter, MLReproAdapter, CompBioAdapter, MaterialsAdapter,
                BioInfoAdapter, ChemistryAdapter, PhysicsAdapter,
                GenomicsAdapter, EpidemiologyAdapter, SystemsBiologyAdapter,
                ImmunoinformaticsAdapter, MetabolomicsAdapter]:
        register_adapter(cls())


_register_all()

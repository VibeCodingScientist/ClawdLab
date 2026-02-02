"""Computational Biology Verification Engine.

This module provides verification of computational biology claims including:
- Protein structure prediction (ESMFold, AlphaFold, Chai-1)
- Protein design verification (pLDDT, pTM, designability)
- Binder design verification (interface analysis, binding prediction)
- Protein novelty checking (BLAST, Foldseek)

The engine is MCP-aware and can integrate with external tools via
the Model Context Protocol for enhanced capabilities.
"""

from platform.verification_engines.compbio_verifier.base import (
    BaseCompBioVerifier,
    BinderResult,
    CompBioVerificationResult,
    DesignResult,
    HybridToolProvider,
    LocalToolProvider,
    MCPToolInfo,
    MCPToolProvider,
    NoveltyResult,
    ProteinComplex,
    ProteinStructure,
    StructureQuality,
    VerificationStatus,
)
from platform.verification_engines.compbio_verifier.config import (
    COMPBIO_CLAIM_TYPES,
    DESIGN_TOOLS,
    STRUCTURE_PREDICTORS,
    get_settings,
)

__all__ = [
    # Config
    "get_settings",
    "STRUCTURE_PREDICTORS",
    "DESIGN_TOOLS",
    "COMPBIO_CLAIM_TYPES",
    # MCP
    "MCPToolProvider",
    "MCPToolInfo",
    "LocalToolProvider",
    "HybridToolProvider",
    # Base classes
    "BaseCompBioVerifier",
    "VerificationStatus",
    "StructureQuality",
    # Data classes
    "ProteinStructure",
    "ProteinComplex",
    "DesignResult",
    "BinderResult",
    "NoveltyResult",
    "CompBioVerificationResult",
]

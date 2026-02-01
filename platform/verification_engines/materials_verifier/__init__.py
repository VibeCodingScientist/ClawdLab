"""Materials Science Verification Engine.

This module provides verification of materials science claims including:
- Crystal structure validation (CIF parsing, symmetry analysis)
- Thermodynamic stability (energy above hull via MLIPs)
- Property prediction verification
- Materials novelty checking (MP, AFLOW, OQMD)

The engine is MCP-aware and can integrate with external tools via
the Model Context Protocol for enhanced capabilities.
"""

from platform.verification_engines.materials_verifier.base import (
    AtomSite,
    BaseMaterialsVerifier,
    CrystalStructure,
    CrystalSystem,
    EnergyResult,
    HybridToolProvider,
    LatticeParameters,
    LocalToolProvider,
    MaterialsNoveltyResult,
    MaterialsVerificationResult,
    MCPToolInfo,
    MCPToolProvider,
    PropertyPrediction,
    SimilarMaterial,
    StabilityClass,
    StabilityResult,
    VerificationStatus,
)
from platform.verification_engines.materials_verifier.config import (
    MATERIALS_CLAIM_TYPES,
    MLIP_MODELS,
    PROPERTY_TYPES,
    get_settings,
)
from platform.verification_engines.materials_verifier.materials_project import (
    MaterialsProjectClient,
    MPMaterial,
)
from platform.verification_engines.materials_verifier.mlip_service import MLIPService
from platform.verification_engines.materials_verifier.novelty_checker import (
    AFLOWClient,
    MaterialsNoveltyChecker,
    OQMDClient,
)
from platform.verification_engines.materials_verifier.service import (
    MaterialsVerificationService,
)
from platform.verification_engines.materials_verifier.structure_tools import (
    CIFParser,
    StructureComparator,
    StructureValidator,
    SymmetryAnalyzer,
    parse_cif,
)

__all__ = [
    # Config
    "get_settings",
    "MLIP_MODELS",
    "PROPERTY_TYPES",
    "MATERIALS_CLAIM_TYPES",
    # MCP
    "MCPToolProvider",
    "MCPToolInfo",
    "LocalToolProvider",
    "HybridToolProvider",
    # Base classes
    "BaseMaterialsVerifier",
    "VerificationStatus",
    "StabilityClass",
    "CrystalSystem",
    # Data classes
    "LatticeParameters",
    "AtomSite",
    "CrystalStructure",
    "EnergyResult",
    "StabilityResult",
    "PropertyPrediction",
    "SimilarMaterial",
    "MaterialsNoveltyResult",
    "MaterialsVerificationResult",
    # Services
    "MaterialsVerificationService",
    "MLIPService",
    "MaterialsProjectClient",
    "MPMaterial",
    "MaterialsNoveltyChecker",
    "AFLOWClient",
    "OQMDClient",
    # Structure tools
    "CIFParser",
    "StructureValidator",
    "SymmetryAnalyzer",
    "StructureComparator",
    "parse_cif",
]

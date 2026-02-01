"""Base classes and data structures for Materials Science verification."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from platform.verification_engines.compbio_verifier.base import (
    HybridToolProvider,
    LocalToolProvider,
    MCPToolInfo,
    MCPToolProvider,
)


class VerificationStatus(Enum):
    """Status of materials verification."""

    VERIFIED = "verified"
    REFUTED = "refuted"
    PARTIAL = "partial"
    INCONCLUSIVE = "inconclusive"
    ERROR = "error"
    PENDING = "pending"


class StabilityClass(Enum):
    """Thermodynamic stability classification."""

    STABLE = "stable"  # On the convex hull
    METASTABLE = "metastable"  # Slightly above hull
    UNSTABLE = "unstable"  # Significantly above hull
    UNKNOWN = "unknown"


class CrystalSystem(Enum):
    """Crystal system classification."""

    TRICLINIC = "triclinic"
    MONOCLINIC = "monoclinic"
    ORTHORHOMBIC = "orthorhombic"
    TETRAGONAL = "tetragonal"
    TRIGONAL = "trigonal"
    HEXAGONAL = "hexagonal"
    CUBIC = "cubic"


# ===========================================
# CRYSTAL STRUCTURE DATA CLASSES
# ===========================================


@dataclass
class LatticeParameters:
    """Lattice parameters of a crystal."""

    a: float  # Å
    b: float  # Å
    c: float  # Å
    alpha: float  # degrees
    beta: float  # degrees
    gamma: float  # degrees
    volume: float | None = None  # Å³

    def __post_init__(self):
        if self.volume is None:
            import math
            # Calculate volume from parameters
            cos_alpha = math.cos(math.radians(self.alpha))
            cos_beta = math.cos(math.radians(self.beta))
            cos_gamma = math.cos(math.radians(self.gamma))
            sin_gamma = math.sin(math.radians(self.gamma))

            self.volume = self.a * self.b * self.c * math.sqrt(
                1 - cos_alpha**2 - cos_beta**2 - cos_gamma**2 +
                2 * cos_alpha * cos_beta * cos_gamma
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "a": self.a,
            "b": self.b,
            "c": self.c,
            "alpha": self.alpha,
            "beta": self.beta,
            "gamma": self.gamma,
            "volume": self.volume,
        }


@dataclass
class AtomSite:
    """Atomic site in a crystal structure."""

    species: str
    x: float  # Fractional coordinate
    y: float  # Fractional coordinate
    z: float  # Fractional coordinate
    occupancy: float = 1.0
    wyckoff: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "species": self.species,
            "coords": [self.x, self.y, self.z],
            "occupancy": self.occupancy,
            "wyckoff": self.wyckoff,
        }


@dataclass
class CrystalStructure:
    """Crystal structure representation."""

    composition: str  # Chemical formula
    lattice: LatticeParameters
    sites: list[AtomSite]
    space_group: str | None = None
    space_group_number: int | None = None
    crystal_system: CrystalSystem | None = None
    cif_string: str | None = None
    source: str = ""  # Where this structure came from

    @property
    def num_atoms(self) -> int:
        return len(self.sites)

    @property
    def volume_per_atom(self) -> float:
        if self.lattice.volume and self.num_atoms > 0:
            return self.lattice.volume / self.num_atoms
        return 0.0

    @property
    def density(self) -> float | None:
        """Calculate density in g/cm³."""
        if not self.lattice.volume:
            return None

        # Would need atomic masses - placeholder
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "composition": self.composition,
            "lattice": self.lattice.to_dict(),
            "sites": [s.to_dict() for s in self.sites],
            "num_atoms": self.num_atoms,
            "space_group": self.space_group,
            "space_group_number": self.space_group_number,
            "crystal_system": self.crystal_system.value if self.crystal_system else None,
            "volume_per_atom": self.volume_per_atom,
            "source": self.source,
        }


# ===========================================
# ENERGY AND STABILITY DATA CLASSES
# ===========================================


@dataclass
class EnergyResult:
    """Result of energy calculation."""

    total_energy: float  # eV
    energy_per_atom: float  # eV/atom
    forces: list[list[float]] | None = None  # eV/Å
    stress: list[list[float]] | None = None  # eV/Å³
    model_used: str = ""
    calculation_time_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_energy_ev": self.total_energy,
            "energy_per_atom_ev": self.energy_per_atom,
            "has_forces": self.forces is not None,
            "has_stress": self.stress is not None,
            "model_used": self.model_used,
            "calculation_time_seconds": self.calculation_time_seconds,
        }


@dataclass
class StabilityResult:
    """Result of stability analysis."""

    energy_above_hull: float  # eV/atom
    stability_class: StabilityClass
    decomposition_products: list[str] = field(default_factory=list)
    decomposition_energies: list[float] = field(default_factory=list)
    competing_phases: list[str] = field(default_factory=list)
    formation_energy: float | None = None  # eV/atom
    is_stable: bool = False
    is_metastable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "energy_above_hull_ev": self.energy_above_hull,
            "stability_class": self.stability_class.value,
            "is_stable": self.is_stable,
            "is_metastable": self.is_metastable,
            "formation_energy_ev": self.formation_energy,
            "decomposition_products": self.decomposition_products,
            "competing_phases": self.competing_phases,
        }


@dataclass
class PropertyPrediction:
    """Predicted material property."""

    property_name: str
    value: float
    unit: str
    uncertainty: float | None = None
    method: str = ""
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "property": self.property_name,
            "value": self.value,
            "unit": self.unit,
            "uncertainty": self.uncertainty,
            "method": self.method,
            "confidence": self.confidence,
        }


# ===========================================
# NOVELTY AND SIMILARITY DATA CLASSES
# ===========================================


@dataclass
class SimilarMaterial:
    """A similar material from database search."""

    material_id: str
    formula: str
    source_database: str  # "mp", "aflow", "oqmd", "icsd"
    space_group: str | None = None
    energy_above_hull: float | None = None
    structure_similarity: float | None = None  # 0-1
    url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "material_id": self.material_id,
            "formula": self.formula,
            "source": self.source_database,
            "space_group": self.space_group,
            "energy_above_hull": self.energy_above_hull,
            "similarity": self.structure_similarity,
            "url": self.url,
        }


@dataclass
class MaterialsNoveltyResult:
    """Result of materials novelty checking."""

    is_novel: bool
    novelty_score: float  # 0.0 = known, 1.0 = completely novel
    similar_materials: list[SimilarMaterial]
    closest_match: SimilarMaterial | None = None
    composition_novel: bool = True
    structure_novel: bool = True
    analysis: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_novel": self.is_novel,
            "novelty_score": self.novelty_score,
            "composition_novel": self.composition_novel,
            "structure_novel": self.structure_novel,
            "similar_materials": [m.to_dict() for m in self.similar_materials],
            "closest_match": self.closest_match.to_dict() if self.closest_match else None,
            "analysis": self.analysis,
        }


# ===========================================
# VERIFICATION RESULT
# ===========================================


@dataclass
class MaterialsVerificationResult:
    """Complete result of materials verification."""

    status: VerificationStatus
    verified: bool
    message: str
    claim_id: str = ""
    claim_type: str = ""

    # Structure
    structure: CrystalStructure | None = None
    structure_valid: bool = False

    # Energy and stability
    energy: EnergyResult | None = None
    stability: StabilityResult | None = None

    # Properties
    properties: list[PropertyPrediction] = field(default_factory=list)

    # Novelty
    novelty: MaterialsNoveltyResult | None = None

    # Timestamps
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Error details
    error_type: str | None = None
    error_details: str | None = None

    # MCP tool usage
    tools_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "verified": self.verified,
            "message": self.message,
            "claim_id": self.claim_id,
            "claim_type": self.claim_type,
            "structure": self.structure.to_dict() if self.structure else None,
            "structure_valid": self.structure_valid,
            "energy": self.energy.to_dict() if self.energy else None,
            "stability": self.stability.to_dict() if self.stability else None,
            "properties": [p.to_dict() for p in self.properties],
            "novelty": self.novelty.to_dict() if self.novelty else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_type": self.error_type,
            "error_details": self.error_details,
            "tools_used": self.tools_used,
        }


# ===========================================
# BASE VERIFIER CLASS
# ===========================================


class BaseMaterialsVerifier(ABC):
    """Abstract base class for Materials verification components."""

    def __init__(self, tool_provider: MCPToolProvider | None = None):
        """
        Initialize verifier with optional MCP tool provider.

        Args:
            tool_provider: MCP tool provider for external tool access
        """
        self._tool_provider = tool_provider or LocalToolProvider()

    @property
    @abstractmethod
    def component_name(self) -> str:
        """Name of this verification component."""
        pass

    @abstractmethod
    async def verify(self, *args, **kwargs) -> Any:
        """Perform verification and return result."""
        pass

    async def _invoke_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Invoke a tool via the tool provider."""
        return await self._tool_provider.invoke_tool(tool_name, parameters, timeout)

    async def _has_tool(self, tool_name: str) -> bool:
        """Check if a tool is available."""
        return await self._tool_provider.has_tool(tool_name)


# Re-export MCP classes for convenience
__all__ = [
    "MCPToolProvider",
    "MCPToolInfo",
    "LocalToolProvider",
    "HybridToolProvider",
    "BaseMaterialsVerifier",
    "VerificationStatus",
    "StabilityClass",
    "CrystalSystem",
    "LatticeParameters",
    "AtomSite",
    "CrystalStructure",
    "EnergyResult",
    "StabilityResult",
    "PropertyPrediction",
    "SimilarMaterial",
    "MaterialsNoveltyResult",
    "MaterialsVerificationResult",
]

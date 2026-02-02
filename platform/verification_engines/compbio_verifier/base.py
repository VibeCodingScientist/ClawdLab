"""Base classes and data structures for CompBio verification with MCP support."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Protocol


class VerificationStatus(Enum):
    """Status of CompBio verification."""

    VERIFIED = "verified"
    REFUTED = "refuted"
    PARTIAL = "partial"
    INCONCLUSIVE = "inconclusive"
    ERROR = "error"
    PENDING = "pending"


class StructureQuality(Enum):
    """Quality levels for structure predictions."""

    HIGH = "high"  # pLDDT > 90
    CONFIDENT = "confident"  # pLDDT 70-90
    LOW = "low"  # pLDDT 50-70
    VERY_LOW = "very_low"  # pLDDT < 50


# ===========================================
# MCP TOOL PROVIDER INTERFACE
# ===========================================


class MCPToolCapability(Protocol):
    """Protocol for MCP tool capabilities."""

    @property
    def tool_name(self) -> str:
        """Name of the MCP tool."""
        ...

    @property
    def description(self) -> str:
        """Description of what the tool does."""
        ...

    async def invoke(self, **kwargs) -> dict[str, Any]:
        """Invoke the MCP tool with given parameters."""
        ...


@dataclass
class MCPToolInfo:
    """Information about an available MCP tool."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None = None
    provider: str = "unknown"
    version: str = "1.0"
    capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "provider": self.provider,
            "version": self.version,
            "capabilities": self.capabilities,
        }


class MCPToolProvider(ABC):
    """
    Abstract base class for MCP tool providers.

    Allows the CompBio verifier to discover and use external tools
    provided via MCP (Model Context Protocol).
    """

    @abstractmethod
    async def discover_tools(self) -> list[MCPToolInfo]:
        """Discover available MCP tools."""
        pass

    @abstractmethod
    async def has_tool(self, tool_name: str) -> bool:
        """Check if a specific tool is available."""
        pass

    @abstractmethod
    async def invoke_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Invoke an MCP tool with given parameters."""
        pass

    @abstractmethod
    async def get_tool_info(self, tool_name: str) -> MCPToolInfo | None:
        """Get information about a specific tool."""
        pass


class LocalToolProvider(MCPToolProvider):
    """
    Local tool provider that executes tools directly.

    Used as fallback when MCP tools are not available.
    """

    def __init__(self):
        self._tools: dict[str, Callable] = {}
        self._tool_info: dict[str, MCPToolInfo] = {}

    def register_tool(
        self,
        name: str,
        func: Callable,
        description: str,
        input_schema: dict[str, Any],
    ) -> None:
        """Register a local tool."""
        self._tools[name] = func
        self._tool_info[name] = MCPToolInfo(
            name=name,
            description=description,
            input_schema=input_schema,
            provider="local",
        )

    async def discover_tools(self) -> list[MCPToolInfo]:
        return list(self._tool_info.values())

    async def has_tool(self, tool_name: str) -> bool:
        return tool_name in self._tools

    async def invoke_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        timeout: int | None = None,
    ) -> dict[str, Any]:
        if tool_name not in self._tools:
            raise ValueError(f"Tool not found: {tool_name}")

        func = self._tools[tool_name]
        # Handle both sync and async functions
        import asyncio
        import inspect

        if inspect.iscoroutinefunction(func):
            return await func(**parameters)
        else:
            return await asyncio.to_thread(func, **parameters)

    async def get_tool_info(self, tool_name: str) -> MCPToolInfo | None:
        return self._tool_info.get(tool_name)


class HybridToolProvider(MCPToolProvider):
    """
    Hybrid tool provider that checks MCP first, then falls back to local.

    This allows seamless integration of MCP tools while maintaining
    local fallback capabilities.
    """

    def __init__(
        self,
        mcp_provider: MCPToolProvider | None = None,
        local_provider: LocalToolProvider | None = None,
        prefer_mcp: bool = True,
    ):
        self._mcp = mcp_provider
        self._local = local_provider or LocalToolProvider()
        self._prefer_mcp = prefer_mcp
        self._tool_cache: dict[str, MCPToolInfo] = {}

    async def discover_tools(self) -> list[MCPToolInfo]:
        tools = []

        # Discover local tools
        local_tools = await self._local.discover_tools()
        tools.extend(local_tools)

        # Discover MCP tools
        if self._mcp:
            try:
                mcp_tools = await self._mcp.discover_tools()
                tools.extend(mcp_tools)
            except Exception:
                pass  # MCP discovery failed, use local only

        return tools

    async def has_tool(self, tool_name: str) -> bool:
        if await self._local.has_tool(tool_name):
            return True
        if self._mcp:
            return await self._mcp.has_tool(tool_name)
        return False

    async def invoke_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        timeout: int | None = None,
    ) -> dict[str, Any]:
        # Check preference and availability
        if self._prefer_mcp and self._mcp:
            if await self._mcp.has_tool(tool_name):
                return await self._mcp.invoke_tool(tool_name, parameters, timeout)

        # Fall back to local
        if await self._local.has_tool(tool_name):
            return await self._local.invoke_tool(tool_name, parameters, timeout)

        # Try MCP if not preferring it but local doesn't have it
        if self._mcp and await self._mcp.has_tool(tool_name):
            return await self._mcp.invoke_tool(tool_name, parameters, timeout)

        raise ValueError(f"Tool not found in any provider: {tool_name}")

    async def get_tool_info(self, tool_name: str) -> MCPToolInfo | None:
        # Check local first
        info = await self._local.get_tool_info(tool_name)
        if info:
            return info

        # Check MCP
        if self._mcp:
            return await self._mcp.get_tool_info(tool_name)

        return None


# ===========================================
# PROTEIN DATA STRUCTURES
# ===========================================


@dataclass
class Residue:
    """Single amino acid residue."""

    index: int
    name: str  # Three-letter code
    chain: str
    plddt: float | None = None
    x: float | None = None
    y: float | None = None
    z: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "chain": self.chain,
            "plddt": self.plddt,
            "coordinates": [self.x, self.y, self.z] if self.x else None,
        }


@dataclass
class ProteinStructure:
    """Protein structure with confidence scores."""

    sequence: str
    pdb_string: str | None = None
    mean_plddt: float = 0.0
    per_residue_plddt: list[float] = field(default_factory=list)
    ptm_score: float | None = None
    predicted_aligned_error: list[list[float]] | None = None
    chains: list[str] = field(default_factory=list)
    num_residues: int = 0
    model_used: str = ""
    prediction_time_seconds: float = 0.0

    def __post_init__(self):
        if not self.num_residues:
            self.num_residues = len(self.sequence)
        if not self.chains:
            self.chains = ["A"]

    @property
    def quality(self) -> StructureQuality:
        """Assess structure quality based on pLDDT."""
        if self.mean_plddt >= 90:
            return StructureQuality.HIGH
        elif self.mean_plddt >= 70:
            return StructureQuality.CONFIDENT
        elif self.mean_plddt >= 50:
            return StructureQuality.LOW
        else:
            return StructureQuality.VERY_LOW

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "sequence_length": len(self.sequence),
            "mean_plddt": self.mean_plddt,
            "ptm_score": self.ptm_score,
            "quality": self.quality.value,
            "chains": self.chains,
            "num_residues": self.num_residues,
            "model_used": self.model_used,
            "prediction_time_seconds": self.prediction_time_seconds,
            "has_pdb": self.pdb_string is not None,
            "has_pae": self.predicted_aligned_error is not None,
        }


@dataclass
class ProteinComplex:
    """Multi-chain protein complex."""

    structures: list[ProteinStructure]
    interface_pae: float | None = None
    iptm_score: float | None = None
    chain_pairs: list[tuple[str, str]] = field(default_factory=list)
    interface_residues: dict[str, list[int]] = field(default_factory=dict)

    @property
    def num_chains(self) -> int:
        return len(self.structures)

    def to_dict(self) -> dict[str, Any]:
        return {
            "num_chains": self.num_chains,
            "chains": [s.to_dict() for s in self.structures],
            "interface_pae": self.interface_pae,
            "iptm_score": self.iptm_score,
            "chain_pairs": self.chain_pairs,
        }


@dataclass
class DesignResult:
    """Result of protein design."""

    designed_sequence: str
    original_sequence: str | None = None
    structure: ProteinStructure | None = None
    sequence_recovery: float | None = None
    self_consistency_score: float | None = None
    design_method: str = ""
    sampling_temperature: float = 0.1
    design_constraints: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "designed_sequence": self.designed_sequence,
            "sequence_length": len(self.designed_sequence),
            "original_sequence": self.original_sequence,
            "sequence_recovery": self.sequence_recovery,
            "self_consistency_score": self.self_consistency_score,
            "design_method": self.design_method,
            "structure": self.structure.to_dict() if self.structure else None,
        }


@dataclass
class BinderResult:
    """Result of binder design verification."""

    binder_sequence: str
    target_structure: ProteinStructure | None
    complex_structure: ProteinComplex | None = None
    interface_plddt: float | None = None
    interface_pae: float | None = None
    num_interface_contacts: int = 0
    interface_area: float | None = None
    binding_energy_estimate: float | None = None
    hotspot_residues: list[int] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "binder_sequence": self.binder_sequence,
            "binder_length": len(self.binder_sequence),
            "interface_plddt": self.interface_plddt,
            "interface_pae": self.interface_pae,
            "num_interface_contacts": self.num_interface_contacts,
            "interface_area": self.interface_area,
            "binding_energy_estimate": self.binding_energy_estimate,
            "hotspot_residues": self.hotspot_residues,
        }


@dataclass
class NoveltyResult:
    """Result of protein novelty checking."""

    is_novel: bool
    novelty_score: float  # 0.0 = known, 1.0 = completely novel
    closest_pdb_id: str | None = None
    closest_uniprot_id: str | None = None
    sequence_identity: float | None = None
    structural_similarity: float | None = None  # TM-score
    blast_hits: list[dict[str, Any]] = field(default_factory=list)
    foldseek_hits: list[dict[str, Any]] = field(default_factory=list)
    analysis: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_novel": self.is_novel,
            "novelty_score": self.novelty_score,
            "closest_pdb_id": self.closest_pdb_id,
            "closest_uniprot_id": self.closest_uniprot_id,
            "sequence_identity": self.sequence_identity,
            "structural_similarity": self.structural_similarity,
            "blast_hits_count": len(self.blast_hits),
            "foldseek_hits_count": len(self.foldseek_hits),
            "analysis": self.analysis,
        }


@dataclass
class CompBioVerificationResult:
    """Complete result of computational biology verification."""

    status: VerificationStatus
    verified: bool
    message: str
    claim_id: str = ""
    claim_type: str = ""

    # Structure prediction results
    structure: ProteinStructure | None = None
    complex_structure: ProteinComplex | None = None

    # Design verification results
    design_result: DesignResult | None = None
    binder_result: BinderResult | None = None

    # Novelty results
    novelty: NoveltyResult | None = None

    # Metrics
    mean_plddt: float | None = None
    ptm_score: float | None = None
    sequence_recovery: float | None = None

    # Timestamps
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Error details
    error_type: str | None = None
    error_details: str | None = None

    # MCP tool usage tracking
    tools_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "verified": self.verified,
            "message": self.message,
            "claim_id": self.claim_id,
            "claim_type": self.claim_type,
            "structure": self.structure.to_dict() if self.structure else None,
            "complex": self.complex_structure.to_dict() if self.complex_structure else None,
            "design": self.design_result.to_dict() if self.design_result else None,
            "binder": self.binder_result.to_dict() if self.binder_result else None,
            "novelty": self.novelty.to_dict() if self.novelty else None,
            "metrics": {
                "mean_plddt": self.mean_plddt,
                "ptm_score": self.ptm_score,
                "sequence_recovery": self.sequence_recovery,
            },
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_type": self.error_type,
            "error_details": self.error_details,
            "tools_used": self.tools_used,
        }


# ===========================================
# BASE VERIFIER CLASSES
# ===========================================


class BaseCompBioVerifier(ABC):
    """Abstract base class for CompBio verification components."""

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

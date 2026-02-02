"""Configuration for Materials Science verification engine."""

from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings


class MaterialsVerifierSettings(BaseSettings):
    """Settings for materials science verification engine."""

    model_config = {"env_prefix": "MATERIALS_VERIFIER_", "case_sensitive": False}

    # MCP Tool Provider Settings
    mcp_enabled: bool = Field(default=True, description="Enable MCP tool discovery")
    prefer_mcp_tools: bool = Field(default=True, description="Prefer MCP tools over local")

    # MLIP Settings
    default_mlip_model: str = Field(
        default="mace-mp-0",
        description="Default MLIP model (mace-mp-0, chgnet, m3gnet)",
    )
    mlip_device: str = Field(default="cuda", description="Device for MLIP calculations")
    energy_calculation_timeout: int = Field(
        default=300,
        description="Energy calculation timeout in seconds",
    )

    # MACE Settings
    mace_model_path: str = Field(
        default="/models/mace/mace-mp-0-medium.model",
        description="Path to MACE model weights",
    )
    mace_dispersion_correction: bool = Field(
        default=True,
        description="Apply D3 dispersion correction",
    )

    # CHGNet Settings
    chgnet_model: str = Field(
        default="0.3.0",
        description="CHGNet model version",
    )

    # M3GNet Settings
    m3gnet_model: str = Field(
        default="MP-2021.2.8-DIRECT-PES",
        description="M3GNet model version",
    )

    # Stability Settings
    hull_distance_threshold: float = Field(
        default=0.1,
        description="Maximum energy above hull (eV/atom) for metastability",
    )
    stable_threshold: float = Field(
        default=0.025,
        description="Maximum energy above hull (eV/atom) for stability",
    )

    # Structure Validation Settings
    min_distance_threshold: float = Field(
        default=0.5,
        description="Minimum interatomic distance (Å)",
    )
    max_volume_per_atom: float = Field(
        default=100.0,
        description="Maximum volume per atom (Å³)",
    )
    symmetry_tolerance: float = Field(
        default=0.1,
        description="Tolerance for symmetry detection (Å)",
    )

    # Materials Project Settings
    materials_project_api_key: str | None = Field(
        default=None,
        description="Materials Project API key",
    )
    materials_project_endpoint: str = Field(
        default="https://api.materialsproject.org",
        description="Materials Project API endpoint",
    )

    # AFLOW Settings
    aflow_api_endpoint: str = Field(
        default="http://aflowlib.org/API/aflux/",
        description="AFLOW API endpoint",
    )

    # OQMD Settings
    oqmd_api_endpoint: str = Field(
        default="http://oqmd.org/oqmdapi/",
        description="OQMD API endpoint",
    )

    # Novelty Settings
    structure_match_threshold: float = Field(
        default=0.1,
        description="Structure match tolerance (Å)",
    )
    novelty_min_score: float = Field(
        default=0.3,
        description="Minimum novelty score for acceptance",
    )

    # Container Settings
    singularity_image_path: str = Field(
        default="/containers/materials-verifier.sif",
        description="Path to Singularity image",
    )
    use_singularity: bool = Field(
        default=True,
        description="Use Singularity container for execution",
    )


@lru_cache
def get_settings() -> MaterialsVerifierSettings:
    """Get cached Materials verifier settings."""
    return MaterialsVerifierSettings()


# MLIP Models
MLIP_MODELS = {
    "mace-mp-0": {
        "name": "MACE-MP-0",
        "description": "MACE pretrained on Materials Project",
        "accuracy": "high",
        "speed": "medium",
        "mcp_tool_name": "mace_calculate",
    },
    "mace-mp-0-small": {
        "name": "MACE-MP-0 Small",
        "description": "Smaller MACE model for faster calculations",
        "accuracy": "medium",
        "speed": "fast",
        "mcp_tool_name": "mace_calculate",
    },
    "chgnet": {
        "name": "CHGNet",
        "description": "Crystal Hamiltonian Graph Neural Network",
        "accuracy": "high",
        "speed": "medium",
        "mcp_tool_name": "chgnet_calculate",
    },
    "m3gnet": {
        "name": "M3GNet",
        "description": "Materials 3-body Graph Network",
        "accuracy": "medium",
        "speed": "fast",
        "mcp_tool_name": "m3gnet_calculate",
    },
}

# Property Types
PROPERTY_TYPES = {
    "formation_energy": {
        "name": "Formation Energy",
        "unit": "eV/atom",
        "description": "Energy of formation from elements",
    },
    "band_gap": {
        "name": "Band Gap",
        "unit": "eV",
        "description": "Electronic band gap",
    },
    "bulk_modulus": {
        "name": "Bulk Modulus",
        "unit": "GPa",
        "description": "Resistance to compression",
    },
    "shear_modulus": {
        "name": "Shear Modulus",
        "unit": "GPa",
        "description": "Resistance to shear deformation",
    },
    "ionic_conductivity": {
        "name": "Ionic Conductivity",
        "unit": "S/cm",
        "description": "Ion transport capability",
    },
    "thermal_conductivity": {
        "name": "Thermal Conductivity",
        "unit": "W/(m·K)",
        "description": "Heat transport capability",
    },
}

# Claim Types
MATERIALS_CLAIM_TYPES = {
    "structure_prediction": {
        "name": "Crystal Structure Prediction",
        "description": "Prediction of stable crystal structure",
        "required_fields": ["composition", "structure_cif"],
        "optional_fields": ["space_group", "lattice_parameters"],
    },
    "stability_claim": {
        "name": "Stability Claim",
        "description": "Claim about thermodynamic stability",
        "required_fields": ["composition", "structure_cif"],
        "optional_fields": ["energy_above_hull", "competing_phases"],
    },
    "property_prediction": {
        "name": "Property Prediction",
        "description": "Prediction of material property",
        "required_fields": ["composition", "property_type", "predicted_value"],
        "optional_fields": ["structure_cif", "method", "uncertainty"],
    },
    "novel_material": {
        "name": "Novel Material Discovery",
        "description": "Discovery of new material",
        "required_fields": ["composition", "structure_cif"],
        "optional_fields": ["synthesis_route", "target_application"],
    },
}

# Common space groups
COMMON_SPACE_GROUPS = {
    "Fm-3m": {"number": 225, "crystal_system": "cubic", "common_for": ["fcc metals", "rocksalt"]},
    "Im-3m": {"number": 229, "crystal_system": "cubic", "common_for": ["bcc metals"]},
    "Fd-3m": {"number": 227, "crystal_system": "cubic", "common_for": ["diamond", "spinels"]},
    "P6_3/mmc": {"number": 194, "crystal_system": "hexagonal", "common_for": ["hcp metals"]},
    "Pnma": {"number": 62, "crystal_system": "orthorhombic", "common_for": ["perovskites"]},
    "R-3m": {"number": 166, "crystal_system": "trigonal", "common_for": ["layered materials"]},
}

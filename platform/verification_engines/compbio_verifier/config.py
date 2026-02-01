"""Configuration for Computational Biology verification engine."""

from functools import lru_cache
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings


class CompBioVerifierSettings(BaseSettings):
    """Settings for computational biology verification engine."""

    model_config = {"env_prefix": "COMPBIO_VERIFIER_", "case_sensitive": False}

    # MCP Tool Provider Settings
    mcp_enabled: bool = Field(default=True, description="Enable MCP tool discovery")
    mcp_discovery_timeout: int = Field(default=30, description="MCP tool discovery timeout")
    prefer_mcp_tools: bool = Field(
        default=True,
        description="Prefer MCP tools over local execution when available",
    )
    mcp_tool_cache_ttl: int = Field(default=300, description="MCP tool cache TTL in seconds")

    # Structure Prediction Settings
    default_structure_predictor: str = Field(
        default="esmfold",
        description="Default structure predictor (esmfold, alphafold, chai1)",
    )
    structure_prediction_timeout: int = Field(
        default=600,
        description="Structure prediction timeout in seconds",
    )
    max_sequence_length: int = Field(
        default=2048,
        description="Maximum sequence length for structure prediction",
    )

    # AlphaFold settings
    alphafold_model_dir: str = Field(
        default="/data/alphafold/models",
        description="AlphaFold model weights directory",
    )
    alphafold_data_dir: str = Field(
        default="/data/alphafold/databases",
        description="AlphaFold databases directory",
    )

    # ESMFold settings
    esmfold_model: str = Field(
        default="facebook/esmfold_v1",
        description="ESMFold model identifier",
    )
    esmfold_chunk_size: int = Field(
        default=64,
        description="ESMFold chunking for memory efficiency",
    )

    # Design Verification Settings
    min_plddt_threshold: float = Field(
        default=70.0,
        description="Minimum mean pLDDT for design acceptance",
    )
    min_ptm_threshold: float = Field(
        default=0.5,
        description="Minimum pTM score for design acceptance",
    )
    min_sequence_recovery: float = Field(
        default=0.3,
        description="Minimum sequence recovery for self-consistency",
    )

    # Binder Verification Settings
    binder_interface_distance: float = Field(
        default=8.0,
        description="Interface distance cutoff in Angstroms",
    )
    min_interface_contacts: int = Field(
        default=10,
        description="Minimum interface contacts for valid binder",
    )
    min_ipae_threshold: float = Field(
        default=10.0,
        description="Maximum interface PAE for confident prediction",
    )

    # ProteinMPNN Settings
    proteinmpnn_model: str = Field(
        default="v_48_020",
        description="ProteinMPNN model version",
    )
    proteinmpnn_sampling_temp: float = Field(
        default=0.1,
        description="ProteinMPNN sampling temperature",
    )
    proteinmpnn_num_samples: int = Field(
        default=4,
        description="Number of sequences to sample",
    )

    # Novelty Checking Settings
    novelty_blast_evalue: float = Field(
        default=1e-5,
        description="BLAST e-value threshold for homolog detection",
    )
    novelty_foldseek_threshold: float = Field(
        default=0.5,
        description="Foldseek TM-score threshold for structural similarity",
    )
    novelty_min_score: float = Field(
        default=0.3,
        description="Minimum novelty score for acceptance",
    )

    # Database Settings
    pdb_api_url: str = Field(
        default="https://data.rcsb.org/rest/v1",
        description="PDB REST API URL",
    )
    uniprot_api_url: str = Field(
        default="https://rest.uniprot.org",
        description="UniProt REST API URL",
    )
    alphafold_db_url: str = Field(
        default="https://alphafold.ebi.ac.uk/api",
        description="AlphaFold Database API URL",
    )

    # Resource Limits
    max_concurrent_predictions: int = Field(
        default=4,
        description="Maximum concurrent structure predictions",
    )
    gpu_memory_fraction: float = Field(
        default=0.8,
        description="GPU memory fraction to use",
    )

    # Container Settings
    singularity_image_path: str = Field(
        default="/containers/compbio-verifier.sif",
        description="Path to Singularity image",
    )
    use_singularity: bool = Field(
        default=True,
        description="Use Singularity container for execution",
    )


@lru_cache
def get_settings() -> CompBioVerifierSettings:
    """Get cached CompBio verifier settings."""
    return CompBioVerifierSettings()


# Structure Prediction Models
STRUCTURE_PREDICTORS = {
    "esmfold": {
        "name": "ESMFold",
        "description": "Meta's ESM-based structure prediction",
        "max_length": 2048,
        "gpu_required": True,
        "mcp_tool_name": "esmfold_predict",
    },
    "alphafold": {
        "name": "AlphaFold2",
        "description": "DeepMind's AlphaFold2 with MSA",
        "max_length": 2500,
        "gpu_required": True,
        "mcp_tool_name": "alphafold_predict",
    },
    "chai1": {
        "name": "Chai-1",
        "description": "Chai Discovery's structure prediction",
        "max_length": 4096,
        "gpu_required": True,
        "mcp_tool_name": "chai1_predict",
    },
    "openfold": {
        "name": "OpenFold",
        "description": "Open-source AlphaFold implementation",
        "max_length": 2500,
        "gpu_required": True,
        "mcp_tool_name": "openfold_predict",
    },
}

# Design Tools
DESIGN_TOOLS = {
    "proteinmpnn": {
        "name": "ProteinMPNN",
        "description": "Message Passing Neural Network for protein design",
        "mcp_tool_name": "proteinmpnn_design",
    },
    "rfdiffusion": {
        "name": "RFdiffusion",
        "description": "Diffusion-based protein design",
        "mcp_tool_name": "rfdiffusion_design",
    },
    "ligandmpnn": {
        "name": "LigandMPNN",
        "description": "Ligand-aware protein design",
        "mcp_tool_name": "ligandmpnn_design",
    },
}

# Docking Tools
DOCKING_TOOLS = {
    "diffdock": {
        "name": "DiffDock",
        "description": "Diffusion-based molecular docking",
        "mcp_tool_name": "diffdock_dock",
    },
    "vina": {
        "name": "AutoDock Vina",
        "description": "Classical molecular docking",
        "mcp_tool_name": "autodock_vina",
    },
}

# Claim Types
COMPBIO_CLAIM_TYPES = {
    "protein_structure": {
        "name": "Protein Structure Prediction",
        "description": "Structure prediction for a protein sequence",
        "required_fields": ["sequence"],
        "optional_fields": ["name", "organism", "function"],
    },
    "protein_design": {
        "name": "Protein Design",
        "description": "De novo protein design or redesign",
        "required_fields": ["target_structure", "design_sequence"],
        "optional_fields": ["design_method", "constraints"],
    },
    "binder_design": {
        "name": "Binder Design",
        "description": "Design of protein binder for target",
        "required_fields": ["target_structure", "binder_sequence"],
        "optional_fields": ["binding_site", "affinity_target"],
    },
    "complex_prediction": {
        "name": "Complex Structure Prediction",
        "description": "Prediction of protein complex structure",
        "required_fields": ["sequences"],
        "optional_fields": ["stoichiometry", "known_interactions"],
    },
}

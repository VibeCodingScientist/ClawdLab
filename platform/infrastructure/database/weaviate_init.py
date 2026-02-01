"""Weaviate schema initialization script."""

from platform.shared.clients.weaviate_client import WeaviateClient, close_client
from platform.shared.utils.logging import get_logger, configure_logging

logger = get_logger(__name__)

# ===========================================
# COLLECTION SCHEMAS
# ===========================================

COLLECTIONS = [
    {
        "name": "Claim",
        "description": "A scientific claim submitted to the platform",
        "properties": [
            {"name": "claim_id", "dataType": ["string"], "description": "Unique claim identifier"},
            {"name": "title", "dataType": ["text"], "description": "Claim title"},
            {"name": "description", "dataType": ["text"], "description": "Claim description"},
            {"name": "domain", "dataType": ["string"], "description": "Research domain"},
            {"name": "claim_type", "dataType": ["string"], "description": "Type of claim"},
            {"name": "verification_status", "dataType": ["string"], "description": "Verification status"},
            {"name": "agent_id", "dataType": ["string"], "description": "Submitting agent ID"},
            {"name": "created_at", "dataType": ["date"], "description": "Creation timestamp"},
        ],
    },
    {
        "name": "Paper",
        "description": "Scientific papers from literature",
        "properties": [
            {"name": "paper_id", "dataType": ["string"], "description": "Unique paper identifier"},
            {"name": "doi", "dataType": ["string"], "description": "Digital Object Identifier"},
            {"name": "arxiv_id", "dataType": ["string"], "description": "arXiv identifier"},
            {"name": "title", "dataType": ["text"], "description": "Paper title"},
            {"name": "abstract", "dataType": ["text"], "description": "Paper abstract"},
            {"name": "authors", "dataType": ["string[]"], "description": "List of authors"},
            {"name": "venue", "dataType": ["string"], "description": "Publication venue"},
            {"name": "year", "dataType": ["int"], "description": "Publication year"},
            {"name": "citation_count", "dataType": ["int"], "description": "Number of citations"},
        ],
    },
    {
        "name": "Concept",
        "description": "Scientific concepts for cross-domain reasoning",
        "properties": [
            {"name": "concept_id", "dataType": ["string"], "description": "Unique concept identifier"},
            {"name": "name", "dataType": ["text"], "description": "Concept name"},
            {"name": "description", "dataType": ["text"], "description": "Concept description"},
            {"name": "domain", "dataType": ["string"], "description": "Primary domain"},
            {"name": "aliases", "dataType": ["string[]"], "description": "Alternative names"},
            {"name": "ontology_ids", "dataType": ["string[]"], "description": "Linked ontology IDs"},
        ],
    },
    {
        "name": "Protein",
        "description": "Protein entities",
        "properties": [
            {"name": "uniprot_id", "dataType": ["string"], "description": "UniProt identifier"},
            {"name": "pdb_id", "dataType": ["string"], "description": "PDB identifier"},
            {"name": "name", "dataType": ["text"], "description": "Protein name"},
            {"name": "description", "dataType": ["text"], "description": "Protein description"},
            {"name": "organism", "dataType": ["string"], "description": "Source organism"},
            {"name": "sequence", "dataType": ["string"], "description": "Amino acid sequence"},
            {"name": "function", "dataType": ["text"], "description": "Protein function"},
            {"name": "go_terms", "dataType": ["string[]"], "description": "Gene Ontology terms"},
        ],
    },
    {
        "name": "Material",
        "description": "Materials and crystals",
        "properties": [
            {"name": "mp_id", "dataType": ["string"], "description": "Materials Project ID"},
            {"name": "formula", "dataType": ["string"], "description": "Chemical formula"},
            {"name": "description", "dataType": ["text"], "description": "Material description"},
            {"name": "space_group", "dataType": ["string"], "description": "Space group"},
            {"name": "crystal_system", "dataType": ["string"], "description": "Crystal system"},
            {"name": "band_gap", "dataType": ["number"], "description": "Band gap in eV"},
            {"name": "formation_energy", "dataType": ["number"], "description": "Formation energy"},
        ],
    },
    {
        "name": "Theorem",
        "description": "Mathematical theorems",
        "properties": [
            {"name": "theorem_id", "dataType": ["string"], "description": "Unique theorem identifier"},
            {"name": "name", "dataType": ["text"], "description": "Theorem name"},
            {"name": "statement_natural", "dataType": ["text"], "description": "Natural language statement"},
            {"name": "statement_formal", "dataType": ["string"], "description": "Formal statement"},
            {"name": "proof_system", "dataType": ["string"], "description": "Proof system (Lean, Coq, etc.)"},
            {"name": "mathlib_path", "dataType": ["string"], "description": "Mathlib path if applicable"},
            {"name": "tags", "dataType": ["string[]"], "description": "Mathematical tags"},
        ],
    },
    {
        "name": "Frontier",
        "description": "Open research problems",
        "properties": [
            {"name": "frontier_id", "dataType": ["string"], "description": "Unique frontier identifier"},
            {"name": "title", "dataType": ["text"], "description": "Problem title"},
            {"name": "description", "dataType": ["text"], "description": "Problem description"},
            {"name": "domain", "dataType": ["string"], "description": "Research domain"},
            {"name": "problem_type", "dataType": ["string"], "description": "Type of problem"},
            {"name": "difficulty", "dataType": ["string"], "description": "Difficulty level"},
            {"name": "status", "dataType": ["string"], "description": "Problem status"},
            {"name": "reward", "dataType": ["int"], "description": "Karma reward"},
        ],
    },
    {
        "name": "Gene",
        "description": "Gene entities for bioinformatics",
        "properties": [
            {"name": "gene_id", "dataType": ["string"], "description": "Gene identifier"},
            {"name": "symbol", "dataType": ["string"], "description": "Gene symbol"},
            {"name": "name", "dataType": ["text"], "description": "Gene name"},
            {"name": "description", "dataType": ["text"], "description": "Gene description"},
            {"name": "organism", "dataType": ["string"], "description": "Source organism"},
            {"name": "chromosome", "dataType": ["string"], "description": "Chromosome location"},
        ],
    },
    {
        "name": "Dataset",
        "description": "Scientific datasets",
        "properties": [
            {"name": "dataset_id", "dataType": ["string"], "description": "Unique dataset identifier"},
            {"name": "name", "dataType": ["text"], "description": "Dataset name"},
            {"name": "description", "dataType": ["text"], "description": "Dataset description"},
            {"name": "domain", "dataType": ["string"], "description": "Research domain"},
            {"name": "source", "dataType": ["string"], "description": "Data source"},
            {"name": "size_bytes", "dataType": ["int"], "description": "Dataset size in bytes"},
            {"name": "record_count", "dataType": ["int"], "description": "Number of records"},
        ],
    },
]


def initialize_weaviate_schema() -> None:
    """Initialize Weaviate schema with all collections."""
    client = WeaviateClient()

    logger.info("weaviate_schema_init_starting")

    for collection in COLLECTIONS:
        name = collection["name"]

        # Check if collection exists
        if client.collection_exists(name):
            logger.info("collection_exists_skipping", name=name)
            continue

        # Create collection
        success = client.create_collection(
            name=name,
            description=collection["description"],
            properties=collection["properties"],
        )

        if success:
            logger.info("collection_created", name=name)
        else:
            logger.error("collection_creation_failed", name=name)

    logger.info("weaviate_schema_init_complete")


def verify_weaviate_schema() -> dict:
    """Verify Weaviate schema is properly initialized."""
    client = WeaviateClient()

    existing_collections = []
    missing_collections = []

    for collection in COLLECTIONS:
        name = collection["name"]
        if client.collection_exists(name):
            existing_collections.append(name)
        else:
            missing_collections.append(name)

    return {
        "existing_collections": existing_collections,
        "missing_collections": missing_collections,
        "total_expected": len(COLLECTIONS),
        "total_existing": len(existing_collections),
        "status": "healthy" if not missing_collections else "incomplete",
    }


def reset_weaviate_schema() -> None:
    """Delete and recreate all collections (use with caution!)."""
    client = WeaviateClient()

    logger.warning("weaviate_schema_reset_starting")

    for collection in COLLECTIONS:
        name = collection["name"]
        if client.collection_exists(name):
            client.delete_collection(name)
            logger.info("collection_deleted", name=name)

    # Recreate all collections
    initialize_weaviate_schema()

    logger.warning("weaviate_schema_reset_complete")


def main():
    """Main function to initialize Weaviate schema."""
    configure_logging(level="INFO", json_format=False)

    try:
        initialize_weaviate_schema()
        status = verify_weaviate_schema()
        logger.info("weaviate_schema_verification", **status)
    finally:
        close_client()


if __name__ == "__main__":
    main()

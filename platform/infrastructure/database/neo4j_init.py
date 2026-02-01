"""Neo4j schema initialization script."""

import asyncio
from platform.shared.clients.neo4j_client import Neo4jClient, get_driver, close_driver
from platform.shared.utils.logging import get_logger, configure_logging

logger = get_logger(__name__)

# ===========================================
# CONSTRAINTS
# ===========================================

CONSTRAINTS = [
    # Agent constraints
    "CREATE CONSTRAINT agent_id IF NOT EXISTS FOR (a:Agent) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT agent_public_key IF NOT EXISTS FOR (a:Agent) REQUIRE a.public_key IS UNIQUE",
    # Claim constraints
    "CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (c:Claim) REQUIRE c.id IS UNIQUE",
    # Domain-specific entity constraints
    "CREATE CONSTRAINT protein_uniprot IF NOT EXISTS FOR (p:Protein) REQUIRE p.uniprot_id IS UNIQUE",
    "CREATE CONSTRAINT compound_pubchem IF NOT EXISTS FOR (c:Compound) REQUIRE c.pubchem_id IS UNIQUE",
    "CREATE CONSTRAINT compound_chembl IF NOT EXISTS FOR (c:Compound) REQUIRE c.chembl_id IS UNIQUE",
    "CREATE CONSTRAINT material_mp IF NOT EXISTS FOR (m:Material) REQUIRE m.mp_id IS UNIQUE",
    "CREATE CONSTRAINT theorem_id IF NOT EXISTS FOR (t:Theorem) REQUIRE t.id IS UNIQUE",
    "CREATE CONSTRAINT paper_doi IF NOT EXISTS FOR (p:Paper) REQUIRE p.doi IS UNIQUE",
    "CREATE CONSTRAINT paper_arxiv IF NOT EXISTS FOR (p:Paper) REQUIRE p.arxiv_id IS UNIQUE",
    "CREATE CONSTRAINT dataset_id IF NOT EXISTS FOR (d:Dataset) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT model_id IF NOT EXISTS FOR (m:Model) REQUIRE m.id IS UNIQUE",
    "CREATE CONSTRAINT gene_id IF NOT EXISTS FOR (g:Gene) REQUIRE g.gene_id IS UNIQUE",
    "CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT frontier_id IF NOT EXISTS FOR (f:Frontier) REQUIRE f.id IS UNIQUE",
]

# ===========================================
# INDEXES
# ===========================================

INDEXES = [
    # Claim indexes
    "CREATE INDEX claim_domain IF NOT EXISTS FOR (c:Claim) ON (c.domain)",
    "CREATE INDEX claim_type IF NOT EXISTS FOR (c:Claim) ON (c.claim_type)",
    "CREATE INDEX claim_status IF NOT EXISTS FOR (c:Claim) ON (c.verification_status)",
    "CREATE INDEX claim_created IF NOT EXISTS FOR (c:Claim) ON (c.created_at)",
    # Protein indexes
    "CREATE INDEX protein_name IF NOT EXISTS FOR (p:Protein) ON (p.name)",
    "CREATE INDEX protein_organism IF NOT EXISTS FOR (p:Protein) ON (p.organism)",
    # Compound indexes
    "CREATE INDEX compound_name IF NOT EXISTS FOR (c:Compound) ON (c.name)",
    "CREATE INDEX compound_formula IF NOT EXISTS FOR (c:Compound) ON (c.formula)",
    # Material indexes
    "CREATE INDEX material_formula IF NOT EXISTS FOR (m:Material) ON (m.formula)",
    "CREATE INDEX material_spacegroup IF NOT EXISTS FOR (m:Material) ON (m.space_group)",
    # Theorem indexes
    "CREATE INDEX theorem_name IF NOT EXISTS FOR (t:Theorem) ON (t.name)",
    # Concept indexes
    "CREATE INDEX concept_name IF NOT EXISTS FOR (c:Concept) ON (c.name)",
    "CREATE INDEX concept_domain IF NOT EXISTS FOR (c:Concept) ON (c.domain)",
    # Agent indexes
    "CREATE INDEX agent_karma IF NOT EXISTS FOR (a:Agent) ON (a.total_karma)",
]

# ===========================================
# FULL-TEXT INDEXES
# ===========================================

FULLTEXT_INDEXES = [
    """
    CREATE FULLTEXT INDEX claim_search IF NOT EXISTS
    FOR (c:Claim) ON EACH [c.title, c.description]
    """,
    """
    CREATE FULLTEXT INDEX concept_search IF NOT EXISTS
    FOR (c:Concept) ON EACH [c.name, c.description]
    """,
    """
    CREATE FULLTEXT INDEX protein_search IF NOT EXISTS
    FOR (p:Protein) ON EACH [p.name, p.description, p.function]
    """,
    """
    CREATE FULLTEXT INDEX paper_search IF NOT EXISTS
    FOR (p:Paper) ON EACH [p.title, p.abstract]
    """,
    """
    CREATE FULLTEXT INDEX material_search IF NOT EXISTS
    FOR (m:Material) ON EACH [m.formula, m.description]
    """,
    """
    CREATE FULLTEXT INDEX theorem_search IF NOT EXISTS
    FOR (t:Theorem) ON EACH [t.name, t.statement_natural]
    """,
]


async def initialize_neo4j_schema() -> None:
    """Initialize Neo4j schema with constraints and indexes."""
    client = Neo4jClient()

    logger.info("neo4j_schema_init_starting")

    # Create constraints
    logger.info("creating_constraints", count=len(CONSTRAINTS))
    for constraint in CONSTRAINTS:
        try:
            await client.execute_write(constraint)
            logger.debug("constraint_created", query=constraint[:50])
        except Exception as e:
            # Constraint may already exist
            logger.warning("constraint_creation_skipped", error=str(e)[:100])

    # Create indexes
    logger.info("creating_indexes", count=len(INDEXES))
    for index in INDEXES:
        try:
            await client.execute_write(index)
            logger.debug("index_created", query=index[:50])
        except Exception as e:
            logger.warning("index_creation_skipped", error=str(e)[:100])

    # Create full-text indexes
    logger.info("creating_fulltext_indexes", count=len(FULLTEXT_INDEXES))
    for index in FULLTEXT_INDEXES:
        try:
            await client.execute_write(index)
            logger.debug("fulltext_index_created")
        except Exception as e:
            logger.warning("fulltext_index_creation_skipped", error=str(e)[:100])

    logger.info("neo4j_schema_init_complete")


async def verify_neo4j_schema() -> dict:
    """Verify Neo4j schema is properly initialized."""
    client = Neo4jClient()

    # Get constraint count
    constraints = await client.execute_read("SHOW CONSTRAINTS")
    indexes = await client.execute_read("SHOW INDEXES")

    return {
        "constraints": len(constraints),
        "indexes": len(indexes),
        "status": "healthy" if len(constraints) > 0 else "needs_init",
    }


async def main():
    """Main function to initialize Neo4j schema."""
    configure_logging(level="INFO", json_format=False)

    try:
        await initialize_neo4j_schema()
        status = await verify_neo4j_schema()
        logger.info("neo4j_schema_verification", **status)
    finally:
        await close_driver()


if __name__ == "__main__":
    asyncio.run(main())

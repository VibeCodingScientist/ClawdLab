"""Seed data for development and testing."""

import asyncio
from datetime import datetime
from uuid import uuid4

from sqlalchemy import text

from platform.infrastructure.database.session import get_db_session, init_db, close_db
from platform.shared.utils.logging import get_logger, configure_logging

logger = get_logger(__name__)

# ===========================================
# SYSTEM AGENT
# ===========================================

SYSTEM_AGENT = {
    "id": "00000000-0000-0000-0000-000000000001",
    "public_key": "-----BEGIN PUBLIC KEY-----\nMCowBQYDK2VwAyEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\n-----END PUBLIC KEY-----",
    "display_name": "System",
    "agent_type": "internal",
    "status": "active",
    "metadata": {
        "description": "System agent for automated operations",
        "is_system": True,
    },
}

# ===========================================
# INITIAL RESEARCH FRONTIERS
# ===========================================

INITIAL_FRONTIERS = [
    # Mathematics
    {
        "domain": "mathematics",
        "subdomain": "number_theory",
        "title": "Formalize the proof of Fermat's Last Theorem in Lean 4",
        "description": "Create a complete formalization of Wiles' proof of Fermat's Last Theorem in Lean 4, building on existing Mathlib infrastructure.",
        "problem_type": "formalization",
        "specification": {
            "statement": "For n > 2, there are no three positive integers a, b, c such that a^n + b^n = c^n",
            "required_axioms": ["standard Mathlib axioms"],
            "target_loc": 50000,
        },
        "difficulty_estimate": "very_hard",
        "base_karma_reward": 10000,
        "bonus_multiplier": 2.0,
    },
    {
        "domain": "mathematics",
        "subdomain": "analysis",
        "title": "Prove new bounds on the Riemann zeta function zeros",
        "description": "Improve upon known zero-free regions for the Riemann zeta function. Submit a Lean 4 formalization of the result.",
        "problem_type": "open_conjecture",
        "specification": {
            "current_best": "de la Vallée Poussin region",
            "target": "Any improvement with formal proof",
        },
        "difficulty_estimate": "open_problem",
        "base_karma_reward": 50000,
        "bonus_multiplier": 5.0,
    },
    # Computational Biology
    {
        "domain": "computational_biology",
        "subdomain": "protein_design",
        "title": "Design a novel IL-6 neutralizing binder",
        "description": "Design a de novo protein binder that neutralizes human IL-6 with predicted Kd < 10nM. Must pass AlphaFold2 and Chai-1 validation.",
        "problem_type": "design_challenge",
        "specification": {
            "target_uniprot": "P05231",
            "target_site": "receptor binding interface",
            "max_length": 100,
            "required_metrics": {
                "alphafold_plddt": ">= 85",
                "chai1_ptm": ">= 0.75",
                "predicted_kd_nm": "<= 10",
            },
        },
        "difficulty_estimate": "hard",
        "base_karma_reward": 500,
        "bonus_multiplier": 1.5,
    },
    {
        "domain": "computational_biology",
        "subdomain": "protein_design",
        "title": "Design a thermostable GFP variant",
        "description": "Design a GFP variant with predicted melting temperature > 90°C while maintaining fluorescence properties.",
        "problem_type": "design_challenge",
        "specification": {
            "base_protein": "avGFP",
            "target_tm": 90,
            "maintain_fluorescence": True,
        },
        "difficulty_estimate": "medium",
        "base_karma_reward": 300,
        "bonus_multiplier": 1.0,
    },
    # Materials Science
    {
        "domain": "materials_science",
        "subdomain": "battery_materials",
        "title": "Discover a novel solid-state Li-ion conductor",
        "description": "Predict a novel crystalline material with ionic conductivity > 10 mS/cm at room temperature. Must be thermodynamically stable.",
        "problem_type": "discovery",
        "specification": {
            "target_conductivity_mS_cm": 10,
            "max_energy_above_hull_eV": 0.025,
            "allowed_elements": ["Li", "O", "S", "P", "Cl", "La", "Zr", "Ti"],
        },
        "difficulty_estimate": "hard",
        "base_karma_reward": 600,
        "bonus_multiplier": 1.5,
    },
    {
        "domain": "materials_science",
        "subdomain": "thermoelectrics",
        "title": "Predict a high-ZT thermoelectric material",
        "description": "Predict a novel material with ZT > 2 at 500K. Must be stable and composed of non-toxic elements.",
        "problem_type": "optimization_target",
        "specification": {
            "target_zt": 2.0,
            "temperature_k": 500,
            "exclude_elements": ["Pb", "Te", "Cd", "Hg"],
        },
        "difficulty_estimate": "hard",
        "base_karma_reward": 500,
        "bonus_multiplier": 1.2,
    },
    # ML/AI
    {
        "domain": "ml_ai",
        "subdomain": "benchmark",
        "title": "Beat SOTA on MATH benchmark with open-weights model",
        "description": "Achieve state-of-the-art performance on the MATH benchmark using an open-weights model under 70B parameters.",
        "problem_type": "benchmark_gap",
        "specification": {
            "benchmark": "MATH",
            "metric": "accuracy",
            "current_sota": 0.84,
            "model_constraint": "open-weights, <= 70B params",
        },
        "difficulty_estimate": "hard",
        "base_karma_reward": 400,
        "bonus_multiplier": 1.0,
    },
    # Bioinformatics
    {
        "domain": "bioinformatics",
        "subdomain": "genomics",
        "title": "Replicate key findings from GWAS study on Type 2 Diabetes",
        "description": "Reproduce the analysis pipeline and validate top 10 SNP associations from a major T2D GWAS study.",
        "problem_type": "replication_needed",
        "specification": {
            "reference_study": "doi:10.1038/ng.2383",
            "required_snps": ["rs7903146", "rs12255372", "rs1801282"],
            "p_value_threshold": 5e-8,
        },
        "difficulty_estimate": "medium",
        "base_karma_reward": 200,
        "bonus_multiplier": 1.0,
    },
]

# ===========================================
# DOMAIN TAXONOMY
# ===========================================

DOMAIN_TAXONOMY = {
    "mathematics": {
        "subdomains": [
            "algebra",
            "analysis",
            "number_theory",
            "geometry",
            "topology",
            "combinatorics",
            "logic",
            "probability",
        ],
        "claim_types": ["theorem", "conjecture", "formalization"],
    },
    "ml_ai": {
        "subdomains": [
            "nlp",
            "computer_vision",
            "reinforcement_learning",
            "optimization",
            "generative_models",
            "interpretability",
            "benchmark",
        ],
        "claim_types": ["ml_experiment", "benchmark_result", "dataset"],
    },
    "computational_biology": {
        "subdomains": [
            "protein_design",
            "structure_prediction",
            "drug_discovery",
            "molecular_dynamics",
            "systems_biology",
        ],
        "claim_types": ["protein_design", "binder_design", "structure_prediction"],
    },
    "materials_science": {
        "subdomains": [
            "battery_materials",
            "catalysis",
            "semiconductors",
            "thermoelectrics",
            "superconductors",
            "magnets",
        ],
        "claim_types": ["material_prediction", "material_property"],
    },
    "bioinformatics": {
        "subdomains": [
            "genomics",
            "transcriptomics",
            "proteomics",
            "metagenomics",
            "clinical_informatics",
        ],
        "claim_types": ["pipeline_result", "sequence_annotation", "dataset"],
    },
}

# ===========================================
# GENESIS LABS
# ===========================================

GENESIS_LABS = [
    {
        "slug": "mathematics",
        "name": "Mathematics Lab",
        "description": "Formal mathematics, theorem proving, and conjecture exploration.",
        "governance_type": "democratic",
        "domains": ["mathematics"],
        "visibility": "public",
        "karma_requirement": 0,
    },
    {
        "slug": "ml-ai",
        "name": "ML & AI Lab",
        "description": "Machine learning experiments, benchmarks, and reproducibility.",
        "governance_type": "democratic",
        "domains": ["ml_ai"],
        "visibility": "public",
        "karma_requirement": 0,
    },
    {
        "slug": "computational-biology",
        "name": "Computational Biology Lab",
        "description": "Protein design, structure prediction, and binder engineering.",
        "governance_type": "democratic",
        "domains": ["computational_biology"],
        "visibility": "public",
        "karma_requirement": 0,
    },
    {
        "slug": "materials-science",
        "name": "Materials Science Lab",
        "description": "Materials property prediction, discovery, and characterization.",
        "governance_type": "democratic",
        "domains": ["materials_science"],
        "visibility": "public",
        "karma_requirement": 0,
    },
    {
        "slug": "bioinformatics",
        "name": "Bioinformatics Lab",
        "description": "Genomics pipelines, sequence annotation, and multi-omics analysis.",
        "governance_type": "democratic",
        "domains": ["bioinformatics"],
        "visibility": "public",
        "karma_requirement": 0,
    },
]

# Default role card templates for genesis labs
DEFAULT_ROLE_TEMPLATES = [
    {"archetype": "pi", "pipeline_layer": "synthesis", "max_holders": 1, "min_karma": 100},
    {"archetype": "theorist", "pipeline_layer": "ideation", "max_holders": 5, "min_karma": 50},
    {"archetype": "experimentalist", "pipeline_layer": "computation", "max_holders": 10, "min_karma": 25},
    {"archetype": "critic", "pipeline_layer": "verification", "max_holders": 5, "min_karma": 50},
    {"archetype": "synthesizer", "pipeline_layer": "synthesis", "max_holders": 3, "min_karma": 50},
    {"archetype": "scout", "pipeline_layer": "ideation", "max_holders": 5, "min_karma": 10},
    {"archetype": "mentor", "pipeline_layer": "communication", "max_holders": 3, "min_karma": 75},
    {"archetype": "technician", "pipeline_layer": "computation", "max_holders": 10, "min_karma": 0},
    {"archetype": "generalist", "pipeline_layer": "ideation", "max_holders": 50, "min_karma": 0},
]

# Map domains to genesis lab slugs for claim migration
DOMAIN_TO_LAB_SLUG = {
    "mathematics": "mathematics",
    "ml_ai": "ml-ai",
    "computational_biology": "computational-biology",
    "materials_science": "materials-science",
    "bioinformatics": "bioinformatics",
}


async def seed_system_agent() -> None:
    """Create the system agent."""
    async with get_db_session() as session:
        # Check if system agent exists
        result = await session.execute(
            text("SELECT id FROM agents WHERE id = :id"),
            {"id": SYSTEM_AGENT["id"]},
        )
        if result.fetchone():
            logger.info("system_agent_exists")
            return

        # Create system agent
        await session.execute(
            text("""
                INSERT INTO agents (id, public_key, display_name, agent_type, status, metadata, created_at, updated_at)
                VALUES (:id, :public_key, :display_name, :agent_type, :status, :metadata, NOW(), NOW())
            """),
            {
                "id": SYSTEM_AGENT["id"],
                "public_key": SYSTEM_AGENT["public_key"],
                "display_name": SYSTEM_AGENT["display_name"],
                "agent_type": SYSTEM_AGENT["agent_type"],
                "status": SYSTEM_AGENT["status"],
                "metadata": str(SYSTEM_AGENT["metadata"]).replace("'", '"'),
            },
        )

        # Create reputation record
        await session.execute(
            text("""
                INSERT INTO agent_reputation (agent_id, total_karma, domain_karma)
                VALUES (:agent_id, 0, '{}')
            """),
            {"agent_id": SYSTEM_AGENT["id"]},
        )

        await session.commit()
        logger.info("system_agent_created")


async def seed_frontiers() -> None:
    """Create initial research frontiers."""
    async with get_db_session() as session:
        for frontier in INITIAL_FRONTIERS:
            frontier_id = str(uuid4())

            # Check if similar frontier exists
            result = await session.execute(
                text("SELECT id FROM research_frontiers WHERE title = :title"),
                {"title": frontier["title"]},
            )
            if result.fetchone():
                logger.debug("frontier_exists_skipping", title=frontier["title"][:50])
                continue

            await session.execute(
                text("""
                    INSERT INTO research_frontiers (
                        id, domain, subdomain, title, description, problem_type,
                        specification, difficulty_estimate, base_karma_reward,
                        bonus_multiplier, status, created_by_agent_id, created_at, updated_at
                    ) VALUES (
                        :id, :domain, :subdomain, :title, :description, :problem_type,
                        :specification, :difficulty_estimate, :base_karma_reward,
                        :bonus_multiplier, 'open', :created_by, NOW(), NOW()
                    )
                """),
                {
                    "id": frontier_id,
                    "domain": frontier["domain"],
                    "subdomain": frontier.get("subdomain"),
                    "title": frontier["title"],
                    "description": frontier["description"],
                    "problem_type": frontier["problem_type"],
                    "specification": str(frontier["specification"]).replace("'", '"'),
                    "difficulty_estimate": frontier["difficulty_estimate"],
                    "base_karma_reward": frontier["base_karma_reward"],
                    "bonus_multiplier": frontier["bonus_multiplier"],
                    "created_by": SYSTEM_AGENT["id"],
                },
            )
            logger.info("frontier_created", title=frontier["title"][:50])

        await session.commit()
        logger.info("frontiers_seeded", count=len(INITIAL_FRONTIERS))


async def seed_genesis_labs() -> None:
    """Create genesis labs with default role cards and migrate existing claims."""
    async with get_db_session() as session:
        for lab_def in GENESIS_LABS:
            # Check if lab already exists
            result = await session.execute(
                text("SELECT id FROM labs WHERE slug = :slug"),
                {"slug": lab_def["slug"]},
            )
            if result.fetchone():
                logger.debug("genesis_lab_exists", slug=lab_def["slug"])
                continue

            lab_id = str(uuid4())

            # Create lab
            await session.execute(
                text("""
                    INSERT INTO labs (
                        id, slug, name, description, governance_type,
                        domains, rules, visibility, karma_requirement,
                        created_by, created_at, updated_at
                    ) VALUES (
                        :id, :slug, :name, :description, :governance_type,
                        :domains, :rules, :visibility, :karma_requirement,
                        :created_by, NOW(), NOW()
                    )
                """),
                {
                    "id": lab_id,
                    "slug": lab_def["slug"],
                    "name": lab_def["name"],
                    "description": lab_def["description"],
                    "governance_type": lab_def["governance_type"],
                    "domains": lab_def["domains"],
                    "rules": '{"voting_threshold": 0.5, "quorum_fraction": 0.3, "min_debate_hours": 24}',
                    "visibility": lab_def["visibility"],
                    "karma_requirement": lab_def["karma_requirement"],
                    "created_by": SYSTEM_AGENT["id"],
                },
            )

            # Create default role cards
            for role in DEFAULT_ROLE_TEMPLATES:
                role_id = str(uuid4())
                await session.execute(
                    text("""
                        INSERT INTO lab_role_cards (
                            id, lab_id, archetype, pipeline_layer,
                            max_holders, min_karma, is_active, created_at
                        ) VALUES (
                            :id, :lab_id, :archetype, :pipeline_layer,
                            :max_holders, :min_karma, true, NOW()
                        )
                    """),
                    {
                        "id": role_id,
                        "lab_id": lab_id,
                        "archetype": role["archetype"],
                        "pipeline_layer": role["pipeline_layer"],
                        "max_holders": role["max_holders"],
                        "min_karma": role["min_karma"],
                    },
                )

            # Create system agent PI membership
            membership_id = str(uuid4())
            # Get the PI role card for this lab
            pi_result = await session.execute(
                text("SELECT id FROM lab_role_cards WHERE lab_id = :lab_id AND archetype = 'pi'"),
                {"lab_id": lab_id},
            )
            pi_role = pi_result.fetchone()
            await session.execute(
                text("""
                    INSERT INTO lab_memberships (
                        id, lab_id, agent_id, role_card_id, lab_karma,
                        vote_weight, status, joined_at, updated_at
                    ) VALUES (
                        :id, :lab_id, :agent_id, :role_card_id, 0,
                        1.0, 'active', NOW(), NOW()
                    )
                """),
                {
                    "id": membership_id,
                    "lab_id": lab_id,
                    "agent_id": SYSTEM_AGENT["id"],
                    "role_card_id": str(pi_role[0]) if pi_role else None,
                },
            )

            logger.info("genesis_lab_created", slug=lab_def["slug"])

        # Migrate existing claims to genesis labs by domain
        for domain, lab_slug in DOMAIN_TO_LAB_SLUG.items():
            result = await session.execute(
                text("SELECT id FROM labs WHERE slug = :slug"),
                {"slug": lab_slug},
            )
            lab_row = result.fetchone()
            if lab_row:
                await session.execute(
                    text("""
                        UPDATE claims SET lab_id = :lab_id
                        WHERE domain = :domain AND lab_id IS NULL
                    """),
                    {"lab_id": str(lab_row[0]), "domain": domain},
                )

        # Create generalist memberships for existing agents
        existing_agents = await session.execute(
            text("SELECT id FROM agents WHERE id != :system_id AND status = 'active'"),
            {"system_id": SYSTEM_AGENT["id"]},
        )
        for agent_row in existing_agents.fetchall():
            agent_id = str(agent_row[0])
            # For each genesis lab, create a generalist membership if not exists
            for lab_def in GENESIS_LABS:
                lab_result = await session.execute(
                    text("SELECT id FROM labs WHERE slug = :slug"),
                    {"slug": lab_def["slug"]},
                )
                lab_row = lab_result.fetchone()
                if not lab_row:
                    continue

                lab_id = str(lab_row[0])
                # Check if membership exists
                existing = await session.execute(
                    text("SELECT id FROM lab_memberships WHERE lab_id = :lab_id AND agent_id = :agent_id"),
                    {"lab_id": lab_id, "agent_id": agent_id},
                )
                if existing.fetchone():
                    continue

                # Get generalist role card
                gen_result = await session.execute(
                    text("SELECT id FROM lab_role_cards WHERE lab_id = :lab_id AND archetype = 'generalist' LIMIT 1"),
                    {"lab_id": lab_id},
                )
                gen_role = gen_result.fetchone()

                mem_id = str(uuid4())
                await session.execute(
                    text("""
                        INSERT INTO lab_memberships (
                            id, lab_id, agent_id, role_card_id, lab_karma,
                            vote_weight, status, joined_at, updated_at
                        ) VALUES (
                            :id, :lab_id, :agent_id, :role_card_id, 0,
                            1.0, 'active', NOW(), NOW()
                        )
                    """),
                    {
                        "id": mem_id,
                        "lab_id": lab_id,
                        "agent_id": agent_id,
                        "role_card_id": str(gen_role[0]) if gen_role else None,
                    },
                )

        await session.commit()
        logger.info("genesis_labs_seeded", count=len(GENESIS_LABS))


async def verify_seed_data() -> dict:
    """Verify seed data was created successfully."""
    async with get_db_session() as session:
        # Count agents
        agents_result = await session.execute(text("SELECT COUNT(*) FROM agents"))
        agents_count = agents_result.scalar()

        # Count frontiers
        frontiers_result = await session.execute(text("SELECT COUNT(*) FROM research_frontiers"))
        frontiers_count = frontiers_result.scalar()

        # Count labs
        labs_result = await session.execute(text("SELECT COUNT(*) FROM labs"))
        labs_count = labs_result.scalar()

        return {
            "agents": agents_count,
            "frontiers": frontiers_count,
            "labs": labs_count,
            "status": "healthy" if agents_count > 0 else "needs_seed",
        }


async def main():
    """Main function to seed the database."""
    configure_logging(level="INFO", json_format=False)

    try:
        await init_db()

        logger.info("seeding_database")
        await seed_system_agent()
        await seed_frontiers()
        await seed_genesis_labs()

        status = await verify_seed_data()
        logger.info("seed_verification", **status)
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())

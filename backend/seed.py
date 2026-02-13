"""Seed script — creates sample data for demo environment.

Usage:
    python -m backend.seed
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.auth import generate_agent_keypair, generate_api_token, hash_token
from backend.database import close_db, get_db_session, init_db
from backend.logging_config import configure_logging, get_logger
from backend.models import (
    Agent,
    AgentReputation,
    AgentToken,
    Deployer,
    ForumPost,
    Lab,
    LabMembership,
    Task,
    TaskTypeEnum,
)

logger = get_logger(__name__)

# Pre-generated agent configs
AGENTS = [
    {"display_name": "Dr.Folding", "agent_type": "openclaw", "foundation_model": "claude-opus-4-6"},
    {"display_name": "PaperHound-9", "agent_type": "openclaw", "foundation_model": "claude-sonnet-4-5"},
    {"display_name": "LabRunner-12", "agent_type": "openclaw", "foundation_model": "gpt-4o"},
    {"display_name": "Skepticus-5", "agent_type": "openclaw", "foundation_model": "claude-opus-4-6"},
    {"display_name": "DocWriter-2", "agent_type": "openclaw", "foundation_model": "claude-sonnet-4-5"},
]

FORUM_POSTS = [
    {
        "author_name": "maria_chen",
        "title": "Can entropy correction improve protein folding predictions for IDPs?",
        "body": "Intrinsically disordered proteins (IDPs) are notoriously difficult to predict. Current models underestimate entropy contributions. I'd love to see agents explore entropy correction approaches and benchmark against existing folding models.",
        "domain": "computational_biology",
    },
    {
        "author_name": "ml_researcher_42",
        "title": "Benchmark MoE architectures on long-context reasoning tasks",
        "body": "Mixture-of-experts models claim efficiency gains but how do they perform on reasoning tasks requiring 100k+ context? Need systematic benchmarks across multiple MoE variants with controlled experiments.",
        "domain": "ml_ai",
    },
    {
        "author_name": "lean_fan",
        "title": "Formal verification of Szemeredi's regularity lemma in Lean 4",
        "body": "The regularity lemma is a cornerstone of combinatorics but lacks formal verification. This would be a significant contribution to the Mathlib library and demonstrate AI-assisted formal proof capabilities.",
        "domain": "mathematics",
    },
]


async def seed():
    configure_logging(level="INFO", json_format=False)
    await init_db()

    async with get_db_session() as db:
        # Create deployer
        deployer = Deployer(
            external_id="demo-deployer-001",
            display_name="Demo Deployer",
        )
        db.add(deployer)
        await db.flush()

        # Create agents with keypairs
        agents = []
        tokens = []
        for agent_config in AGENTS:
            private_key, identity = generate_agent_keypair()
            agent = Agent(
                deployer_id=deployer.id,
                public_key=identity.get_public_key_base64(),
                **agent_config,
            )
            db.add(agent)
            await db.flush()

            # Generate token
            raw_token = generate_api_token()
            token = AgentToken(
                agent_id=agent.id,
                token_hash=hash_token(raw_token),
                token_prefix=raw_token[:8],
            )
            db.add(token)

            # Create reputation
            rep = AgentReputation(agent_id=agent.id)
            db.add(rep)

            agents.append(agent)
            tokens.append(raw_token)
            logger.info(
                "agent_seeded",
                name=agent.display_name,
                agent_id=str(agent.id),
                token=raw_token,
            )

        # Create forum posts
        posts = []
        for post_data in FORUM_POSTS:
            post = ForumPost(**post_data)
            db.add(post)
            posts.append(post)
        await db.flush()

        # Create a demo lab from the first forum post
        lab = Lab(
            slug="protein-folding-dynamics",
            name="Protein Folding Dynamics Lab",
            description="Investigating entropy correction approaches for IDP folding predictions",
            governance_type="democratic",
            domains=["computational_biology"],
            forum_post_id=posts[0].id,
            created_by=agents[0].id,
        )
        db.add(lab)
        await db.flush()

        # Update forum post status
        posts[0].status = "claimed"
        posts[0].claimed_by_lab = lab.id

        # Add members with roles
        roles = ["pi", "scout", "research_analyst", "skeptical_theorist", "synthesizer"]
        for agent, role in zip(agents, roles):
            membership = LabMembership(
                lab_id=lab.id,
                agent_id=agent.id,
                role=role,
            )
            db.add(membership)

        await db.flush()

        # Create sample tasks
        task1 = Task(
            lab_id=lab.id,
            title="Literature review: entropy correction methods in protein folding",
            description="Survey recent papers on entropy correction approaches for IDPs",
            task_type=TaskTypeEnum.literature_review,
            domain="computational_biology",
            proposed_by=agents[0].id,
            assigned_to=agents[1].id,
        )
        db.add(task1)

        task2 = Task(
            lab_id=lab.id,
            title="Benchmark entropy-corrected models against AlphaFold predictions",
            description="Run computational benchmarks comparing entropy-corrected folding models with standard AlphaFold for a set of known IDPs",
            task_type=TaskTypeEnum.analysis,
            domain="computational_biology",
            proposed_by=agents[1].id,
        )
        db.add(task2)

        await db.commit()

        logger.info("seed_complete", agent_count=len(agents), lab_slug=lab.slug)

        # Print tokens for easy testing
        print("\n" + "=" * 60)
        print("SEED DATA CREATED SUCCESSFULLY")
        print("=" * 60)
        print(f"\nLab: {lab.name} (slug: {lab.slug})")
        print(f"Lab ID: {lab.id}")
        print(f"\nAgents and tokens:")
        for agent, token in zip(agents, tokens):
            print(f"  {agent.display_name}: {token}")
        print(f"\nForum posts: {len(posts)}")
        print(f"Tasks: 2")
        print("=" * 60)

    await close_db()


if __name__ == "__main__":
    asyncio.run(seed())

"""Add role_cards table, custom_bans on lab_memberships, seed data, agent_levels view.

Revision ID: 004
Revises: 003
Create Date: 2026-02-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create role_cards table
    op.create_table(
        "role_cards",
        sa.Column("role", sa.Text(), primary_key=True),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column(
            "inputs",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "outputs",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "hard_bans",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "escalation",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "task_types_allowed",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "can_initiate_voting",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "can_assign_tasks",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "definition_of_done",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )

    # 2. Add custom_bans to lab_memberships
    op.add_column(
        "lab_memberships",
        sa.Column(
            "custom_bans",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )

    # 3. Seed the 5 role cards
    op.execute("""
        INSERT INTO role_cards (role, domain, inputs, outputs, hard_bans, escalation, task_types_allowed, can_initiate_voting, can_assign_tasks, definition_of_done) VALUES
        ('pi',
         'Lab governance, task prioritization, voting initiation, and quality control.',
         ARRAY['Completed tasks from all roles', 'Critique results from skeptical theorists', 'Forum post context and human feedback'],
         ARRAY['Voting initiation decisions', 'Task priority assignments', 'Lab progress summaries (auto-posted to forum)'],
         ARRAY['No executing research tasks directly — delegate only.', 'No approving own work (conflict of interest).', 'No skipping critique period for high-stakes claims.', 'No fabricating progress summaries.'],
         ARRAY['Conflicting critique results on same task', 'Verification engine failures', 'Lab member disputes (defer to deployer)'],
         '{}',
         true, true,
         ARRAY['Every task has an owner and deadline.', 'Voting initiated only after critique period.']
        ),
        ('scout',
         'Literature discovery, trend identification, and research gap analysis.',
         ARRAY['Forum posts and human ideas', 'Existing lab task results', 'Domain-specific databases and papers'],
         ARRAY['Literature review tasks with structured paper lists', 'Research gap proposals'],
         ARRAY['No fabricating citations or paper references.', 'No proposing analysis tasks — hand off to research analysts.', 'No making claims without sourced evidence.', 'No internal tool traces or raw API responses in outputs.'],
         ARRAY['Contradictory findings across sources', 'Claims requiring domain expertise beyond literature review'],
         ARRAY['literature_review'],
         false, false,
         ARRAY['Papers list includes title, authors, year, and URL for each entry.', 'Summary is at least 50 words with key findings identified.']
        ),
        ('research_analyst',
         'Computation, analysis, experimentation, and verification-ready result production.',
         ARRAY['Literature reviews from scouts', 'PI-assigned research directions', 'Critique feedback requiring revision'],
         ARRAY['Analysis tasks with verifiable results (proofs, benchmarks, structures, pipelines)', 'Deep research with methodology and reproducible artifacts'],
         ARRAY['No fabricating experimental results or metrics.', 'No claiming verification without running verification engine.', 'No skipping methodology description in results.', 'No submitting results that lack reproducibility information.'],
         ARRAY['Inconclusive or ambiguous experimental results', 'Resource requirements exceeding lab capabilities', 'Results contradicting established literature'],
         ARRAY['analysis', 'deep_research'],
         false, false,
         ARRAY['Result includes methodology section.', 'All metrics are reproducible from provided artifacts.', 'Domain-specific verification payload fields are populated.']
        ),
        ('skeptical_theorist',
         'Adversarial review, critique, and competing hypothesis generation.',
         ARRAY['Completed analysis and research tasks', 'Claims pending voting'],
         ARRAY['Critique tasks identifying specific flaws', 'Competing alternative tasks (spawned from critiques)'],
         ARRAY['No approving work without identifying at least one weakness or limitation.', 'No personal attacks on agents — critique the work, not the worker.', 'No fabricating counterarguments — all critiques must be evidence-based.', 'No blocking progress indefinitely — critiques must be actionable.'],
         ARRAY['Fundamental methodological flaws requiring full task rejection', 'Critiques that span multiple tasks (systemic issues)'],
         ARRAY['critique'],
         false, false,
         ARRAY['At least one specific issue identified with evidence.', 'Severity rated as minor/major/critical.', 'Actionable suggestion included for each issue.']
        ),
        ('synthesizer',
         'Cross-task integration, paper drafting, and knowledge consolidation.',
         ARRAY['Accepted analysis results', 'Resolved critiques', 'Literature reviews'],
         ARRAY['Synthesis documents combining multiple task results', 'Draft papers and reports'],
         ARRAY['No synthesizing from rejected or unverified tasks.', 'No adding new claims not present in source tasks.', 'No omitting contradictory findings — synthesis must be balanced.', 'No fabricating connections between unrelated results.'],
         ARRAY['Contradictory accepted results that cannot be reconciled', 'Synthesis spanning multiple domains'],
         ARRAY['synthesis'],
         false, false,
         ARRAY['All source task IDs referenced.', 'Contradictory findings explicitly addressed.', 'Document is at least 100 words.']
        )
    """)

    # 4. Seed role_action_weights — on-role actions get 1.0×, off-role get default 0.3×
    op.execute("""
        INSERT INTO role_action_weights (role, action_type, weight) VALUES
        -- PI: governance actions are on-role
        ('pi', 'verification', 1.0),

        -- Scout: literature is on-role
        ('scout', 'literature_review', 1.0),

        -- Research Analyst: analysis and deep research are on-role
        ('research_analyst', 'analysis', 1.0),
        ('research_analyst', 'verification', 0.8),

        -- Skeptical Theorist: critique is on-role
        ('skeptical_theorist', 'critique', 1.0),

        -- Synthesizer: synthesis is on-role
        ('synthesizer', 'synthesis', 1.0)
        ON CONFLICT DO NOTHING
    """)

    # 5. Create agent_levels view
    op.execute("""
        CREATE OR REPLACE VIEW agent_levels AS
        SELECT
            a.id AS agent_id,
            a.display_name,
            COALESCE(r.vrep, 0) + COALESCE(r.crep, 0) AS total_rep,
            LEAST(15, FLOOR(LN(
                GREATEST(COALESCE(r.vrep, 0) + COALESCE(r.crep, 0), 0) + 1
            ) / LN(2)) + 1)::INT AS level,
            CASE
                WHEN COALESCE(r.vrep, 0) + COALESCE(r.crep, 0) >= 500 THEN 'grandmaster'
                WHEN COALESCE(r.vrep, 0) + COALESCE(r.crep, 0) >= 200 THEN 'master'
                WHEN COALESCE(r.vrep, 0) + COALESCE(r.crep, 0) >= 50  THEN 'expert'
                WHEN COALESCE(r.vrep, 0) + COALESCE(r.crep, 0) >= 15  THEN 'specialist'
                WHEN COALESCE(r.vrep, 0) + COALESCE(r.crep, 0) >= 3   THEN 'contributor'
                ELSE 'novice'
            END AS tier
        FROM agents a
        LEFT JOIN agent_reputation r ON r.agent_id = a.id
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS agent_levels")
    op.drop_table("role_cards")
    op.drop_column("lab_memberships", "custom_bans")

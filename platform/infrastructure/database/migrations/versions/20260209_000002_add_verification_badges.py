"""Add verification badge columns to claims table.

Revision ID: 20260209_002
Revises: 20260209_001
Create Date: 2026-02-09 00:00:02.000000

This migration extends the claims table with three columns that support
the Verification Pipeline v2 badge system:

Schema Changes:
---------------
- claims.verification_badge: VARCHAR(10), nullable
    Traffic-light badge: 'green', 'amber', or 'red'.
    Set by the BadgeCalculator after all verification steps complete.

- claims.stability_score: DECIMAL(5,4), nullable
    Robustness stability score (0.0000 -- 1.0000).
    Measures how sensitive the claim's result is to input perturbations.

- claims.consistency_score: DECIMAL(5,4), nullable
    Consistency confidence score (0.0000 -- 1.0000).
    Measures agreement with previously verified claims in the knowledge
    base.

Indexes:
--------
- idx_claims_badge: B-tree on verification_badge for badge-filtered
  queries (e.g. "show all RED claims").
"""

from alembic import op
import sqlalchemy as sa

revision = "20260209_002"
down_revision = "20260209_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # verification_badge: traffic-light badge colour
    op.add_column(
        "claims",
        sa.Column(
            "verification_badge",
            sa.String(10),
            nullable=True,
        ),
    )

    # stability_score: robustness metric from perturbation testing
    op.add_column(
        "claims",
        sa.Column(
            "stability_score",
            sa.DECIMAL(5, 4),
            nullable=True,
        ),
    )

    # consistency_score: knowledge-base agreement metric
    op.add_column(
        "claims",
        sa.Column(
            "consistency_score",
            sa.DECIMAL(5, 4),
            nullable=True,
        ),
    )

    # Index for filtering by badge colour
    op.create_index(
        "idx_claims_badge",
        "claims",
        ["verification_badge"],
    )


def downgrade() -> None:
    op.drop_index("idx_claims_badge", table_name="claims")
    op.drop_column("claims", "consistency_score")
    op.drop_column("claims", "stability_score")
    op.drop_column("claims", "verification_badge")

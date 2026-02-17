"""Expand ck_forum_domain constraint to include all verification domains.

Adds chemistry, physics, genomics, epidemiology, systems_biology,
immunoinformatics, and metabolomics to the allowed forum post domains.

Revision ID: 012
Revises: 011
Create Date: 2026-02-17
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_DOMAINS = (
    "domain IN ('mathematics','ml_ai','computational_biology',"
    "'materials_science','bioinformatics','general')"
)

NEW_DOMAINS = (
    "domain IN ('mathematics','ml_ai','computational_biology',"
    "'materials_science','bioinformatics','chemistry','physics',"
    "'genomics','epidemiology','systems_biology',"
    "'immunoinformatics','metabolomics','general')"
)


def upgrade() -> None:
    op.drop_constraint("ck_forum_domain", "forum_posts", type_="check")
    op.create_check_constraint("ck_forum_domain", "forum_posts", NEW_DOMAINS)


def downgrade() -> None:
    op.drop_constraint("ck_forum_domain", "forum_posts", type_="check")
    op.create_check_constraint("ck_forum_domain", "forum_posts", OLD_DOMAINS)

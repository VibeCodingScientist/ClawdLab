"""Add user_api_keys table for programmatic API access.

Revision ID: 011
Revises: 010
Create Date: 2026-02-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("token_prefix", sa.Text(), nullable=False),
        sa.Column(
            "scopes",
            sa.ARRAY(sa.String),
            nullable=False,
            server_default=sa.text("'{read,write}'"),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_user_api_keys_prefix", "user_api_keys", ["token_prefix"])
    op.create_index("idx_user_api_keys_user", "user_api_keys", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_user_api_keys_user", table_name="user_api_keys")
    op.drop_index("idx_user_api_keys_prefix", table_name="user_api_keys")
    op.drop_table("user_api_keys")

"""Add user authentication tables.

Revision ID: 20250202_000001
Revises: 20250201_000000
Create Date: 2025-02-02 00:00:01.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20250202_000001"
down_revision: Union[str, None] = "20250201_000000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===========================================
    # USER AUTHENTICATION TABLES
    # ===========================================

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("username", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("roles", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("permissions", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("last_login", sa.DateTime(timezone=True)),
        sa.Column("login_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("idx_users_username", "users", ["username"])
    op.create_index("idx_users_email", "users", ["email"])
    op.create_index("idx_users_status", "users", ["status"])

    # ===========================================
    # USER TOKENS TABLE
    # ===========================================

    op.create_table(
        "user_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_type", sa.String(20), nullable=False),
        sa.Column("token_value", sa.Text(), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_user_tokens_user", "user_tokens", ["user_id"])
    op.create_index("idx_user_tokens_type", "user_tokens", ["token_type"])
    op.create_index("idx_user_tokens_expires", "user_tokens", ["expires_at"])

    # ===========================================
    # USER SESSIONS TABLE
    # ===========================================

    op.create_table(
        "user_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_tokens.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ip_address", sa.String(50), nullable=False, server_default=""),
        sa.Column("user_agent", sa.Text(), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_activity", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_user_sessions_user", "user_sessions", ["user_id"])
    op.create_index("idx_user_sessions_active", "user_sessions", ["user_id", "active"])

    # ===========================================
    # API KEYS TABLE
    # ===========================================

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("scopes", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("rate_limit", sa.Integer()),
        sa.Column("last_used", sa.DateTime(timezone=True)),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()")),
    )
    op.create_index("idx_api_keys_user", "api_keys", ["user_id"])
    op.create_index("idx_api_keys_prefix", "api_keys", ["key_prefix"])
    op.create_index("idx_api_keys_active", "api_keys", ["active"])


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_table("user_sessions")
    op.drop_table("user_tokens")
    op.drop_table("users")

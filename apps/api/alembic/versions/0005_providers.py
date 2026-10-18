"""cloud providers: provider_credentials, messages.provider, messages.finish (all additive, no data loss)

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("messages") as batch:
        batch.add_column(sa.Column("provider", sa.String(16), nullable=True))
        batch.add_column(sa.Column("finish", sa.String(12), nullable=True))

    op.create_table(
        "provider_credentials",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("last4", sa.String(8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "provider", name="uq_provider_credentials_user_provider"),
    )
    op.create_index("ix_provider_credentials_user_id", "provider_credentials", ["user_id"])


def downgrade() -> None:
    op.drop_table("provider_credentials")
    with op.batch_alter_table("messages") as batch:
        batch.drop_column("finish")
        batch.drop_column("provider")

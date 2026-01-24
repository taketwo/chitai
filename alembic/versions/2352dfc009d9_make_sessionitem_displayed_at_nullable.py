"""Make SessionItem.displayed_at nullable

Revision ID: 2352dfc009d9
Revises: 262cba6b5f6f
Create Date: 2026-01-24 20:43:55.141212

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2352dfc009d9"
down_revision: str | Sequence[str] | None = "262cba6b5f6f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite doesn't support ALTER COLUMN, so we use batch operations to
    # recreate the table
    with op.batch_alter_table("session_items", schema=None) as batch_op:
        batch_op.alter_column(
            "displayed_at", existing_type=sa.DATETIME(), nullable=True
        )


def downgrade() -> None:
    """Downgrade schema."""
    # SQLite doesn't support ALTER COLUMN, so we use batch operations to
    # recreate the table
    with op.batch_alter_table("session_items", schema=None) as batch_op:
        batch_op.alter_column(
            "displayed_at", existing_type=sa.DATETIME(), nullable=False
        )

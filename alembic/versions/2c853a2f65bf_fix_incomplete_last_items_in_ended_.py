"""Fix incomplete last items in ended sessions

Revision ID: 2c853a2f65bf
Revises: 322ec5502461
Create Date: 2026-02-12 14:03:48.278704

Data migration to fix historical bug where items were not marked as completed
when sessions ended. This marks the last displayed item in ended sessions as
completed, using the session's end time.

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2c853a2f65bf"
down_revision: str | Sequence[str] | None = "322ec5502461"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Mark last displayed items in ended sessions as completed.

    Fixes historical data where sessions ended but the last item was not marked
    as completed due to a bug in the advance_word/next_item logic. The bug has
    been fixed in application code; this migration cleans up existing data.

    For each session where:
    - The session has ended (ended_at IS NOT NULL)
    - The last displayed item is not completed (completed_at IS NULL)

    Set that item's completed_at to the session's ended_at timestamp.
    """
    op.execute("""
        UPDATE session_items
        SET completed_at = (
            SELECT s.ended_at
            FROM sessions s
            WHERE s.id = session_items.session_id
        )
        WHERE session_items.id IN (
            SELECT si.id
            FROM session_items si
            JOIN sessions s ON si.session_id = s.id
            WHERE s.ended_at IS NOT NULL
              AND si.completed_at IS NULL
              AND si.displayed_at IS NOT NULL
              AND si.displayed_at = (
                  SELECT MAX(si2.displayed_at)
                  FROM session_items si2
                  WHERE si2.session_id = si.session_id
                    AND si2.displayed_at IS NOT NULL
              )
        )
    """)


def downgrade() -> None:
    """Downgrade not supported for data cleanup migrations.

    This migration fixes historical data corruption from a bug. Reversing it
    would reintroduce incorrect data, so downgrade is not supported.
    """
    msg = (
        "Cannot reverse data cleanup migration. "
        "This migration fixes historical bug data and is not reversible."
    )
    raise NotImplementedError(msg)

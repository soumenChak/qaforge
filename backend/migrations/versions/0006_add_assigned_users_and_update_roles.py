"""Add assigned_users JSONB column to projects table. Update existing users
with role 'tester' or 'lead' to 'engineer'.

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add assigned_users JSONB column to projects table
    op.add_column(
        "projects",
        sa.Column(
            "assigned_users",
            JSONB,
            nullable=True,
            comment="List of user UUIDs assigned to this project",
        ),
    )

    # Update existing users: replace 'tester' and 'lead' roles with 'engineer'
    # This handles JSONB arrays — we replace any occurrence of "tester" or "lead"
    # with "engineer" in the roles column.
    conn = op.get_bind()

    # Replace 'tester' with 'engineer' in roles arrays
    conn.execute(
        sa.text("""
            UPDATE users
            SET roles = (
                SELECT jsonb_agg(
                    CASE
                        WHEN elem::text IN ('"tester"', '"lead"') THEN '"engineer"'::jsonb
                        ELSE elem
                    END
                )
                FROM jsonb_array_elements(roles) AS elem
            )
            WHERE roles @> '["tester"]'::jsonb
               OR roles @> '["lead"]'::jsonb
        """)
    )

    # Deduplicate: if a user now has ["engineer", "engineer"], compact to ["engineer"]
    conn.execute(
        sa.text("""
            UPDATE users
            SET roles = (
                SELECT jsonb_agg(DISTINCT elem)
                FROM jsonb_array_elements(roles) AS elem
            )
            WHERE EXISTS (
                SELECT 1
                FROM (
                    SELECT elem, COUNT(*) as cnt
                    FROM jsonb_array_elements(roles) AS elem
                    GROUP BY elem
                    HAVING COUNT(*) > 1
                ) dups
            )
        """)
    )


def downgrade() -> None:
    # Remove assigned_users column
    op.drop_column("projects", "assigned_users")

    # Revert 'engineer' back to 'tester' (best-effort)
    conn = op.get_bind()
    conn.execute(
        sa.text("""
            UPDATE users
            SET roles = (
                SELECT jsonb_agg(
                    CASE
                        WHEN elem::text = '"engineer"' THEN '"tester"'::jsonb
                        ELSE elem
                    END
                )
                FROM jsonb_array_elements(roles) AS elem
            )
            WHERE roles @> '["engineer"]'::jsonb
              AND NOT roles @> '["admin"]'::jsonb
        """)
    )

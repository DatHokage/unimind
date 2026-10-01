"""drop temporary course class backup table

The backup was created by the course_class timeline migration as a one-time
rollback aid. It is no longer needed after the migration has been deployed.

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-09-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BACKUP_TABLE = "course_class_backup_202608"


def upgrade() -> None:
    op.execute(sa.text(f"DROP TABLE IF EXISTS {BACKUP_TABLE}"))


def downgrade() -> None:
    # The backup data was intentionally discarded; it cannot be reconstructed.
    pass

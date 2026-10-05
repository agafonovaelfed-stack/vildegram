"""add is_service to chats

Revision ID: 7f8ca4471cff
Revises: 96d672cd844c
Create Date: 2026-10-04 19:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f8ca4471cff"
down_revision: Union[str, None] = "96d672cd844c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chats",
        sa.Column("is_service", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("chats", "is_service")

"""merge embed and webhook deliveries heads

Revision ID: 5db5d7ba1124
Revises: e5081f86ee1b, 61101cef342e
Create Date: 2026-05-08 18:19:42.198159

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '5db5d7ba1124'
down_revision: Union[str, None] = ('e5081f86ee1b', '61101cef342e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

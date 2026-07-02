"""add_nav_message_id

Revision ID: a1b2c3d4e5f6
Revises: 68c49c3c8213
Create Date: 2026-06-27 21:54:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '8632fe8dfa46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('players', sa.Column('nav_message_id', sa.BigInteger(), nullable=True), schema='core')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('players', 'nav_message_id', schema='core')

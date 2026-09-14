"""baseline

Marks the schema that already exists in every currently-deployed
environment (users, fund_data), historically created via create_all()
rather than Alembic. Against an existing production database, run
`alembic stamp 8a3c6a4d1e8f` before applying later revisions with
`alembic upgrade head` -- the tables already exist there, so upgrade()
below is a no-op in that case. Against a genuinely fresh database (a new
environment that never ran create_all()), upgrade() creates the two
tables itself so `alembic upgrade head` alone is enough to reach a
working schema.

Revision ID: 8a3c6a4d1e8f
Revises:
Create Date: 2026-09-14 21:54:52.300430

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a3c6a4d1e8f'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = sa.inspect(bind).get_table_names()

    if 'users' not in existing_tables:
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('email', sa.String(length=100), nullable=False),
            sa.Column('password_hash', sa.String(length=255), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('email'),
        )

    if 'fund_data' not in existing_tables:
        op.create_table(
            'fund_data',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=True),
            sa.Column('asset_class', sa.String(length=50), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing_tables = sa.inspect(bind).get_table_names()
    if 'fund_data' in existing_tables:
        op.drop_table('fund_data')
    if 'users' in existing_tables:
        op.drop_table('users')

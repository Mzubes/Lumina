"""add relationship manager to clients and due date to reports

Revision ID: b4e1c9a77d20
Revises: 2741330c4606
Create Date: 2026-09-19 23:20:00.000000

Both columns are additive and nullable, so no batch_alter_table is needed --
that convention is reserved for changing an existing column's type or
nullability, which SQLite can't do in place.

`reports.due_date` has no derivable source (a creation date isn't a deadline,
and workflow diagram nodes carry no target duration), so existing rows are
left NULL rather than backfilled with a guess. Risk/SLA status is computed
from it at read time (backend/risk_status.py); nothing is stored.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4e1c9a77d20'
down_revision: Union[str, None] = '2741330c4606'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('clients', sa.Column('relationship_manager_id', sa.Integer(), nullable=True))
    # Named explicitly: SQLite can't drop an unnamed constraint on downgrade.
    with op.batch_alter_table('clients') as batch_op:
        batch_op.create_foreign_key(
            'fk_clients_relationship_manager_id_users', 'users', ['relationship_manager_id'], ['id'],
        )

    op.add_column('reports', sa.Column('due_date', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('reports', 'due_date')

    with op.batch_alter_table('clients') as batch_op:
        batch_op.drop_constraint('fk_clients_relationship_manager_id_users', type_='foreignkey')
    op.drop_column('clients', 'relationship_manager_id')

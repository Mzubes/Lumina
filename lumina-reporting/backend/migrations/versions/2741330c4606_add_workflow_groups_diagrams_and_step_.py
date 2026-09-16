"""add workflow groups diagrams and step instances

Revision ID: 2741330c4606
Revises: fc92269c93e6
Create Date: 2026-09-15 20:07:34.968699

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2741330c4606'
down_revision: Union[str, None] = 'fc92269c93e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('workflow_groups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('workflow_group_memberships',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['group_id'], ['workflow_groups.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'group_id', name='uq_workflow_group_membership')
    )
    op.create_table('workflow_diagrams',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('template_id', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('nodes', sa.Text(), nullable=False),
    sa.Column('edges', sa.Text(), nullable=False),
    sa.Column('generated', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['template_id'], ['report_templates.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('template_id', 'version', name='uq_workflow_diagram_template_version')
    )
    op.create_table('report_step_instances',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('report_id', sa.Integer(), nullable=False),
    sa.Column('node_id', sa.String(length=64), nullable=False),
    sa.Column('node_name', sa.String(length=150), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=True),
    sa.Column('state', sa.String(length=20), nullable=False),
    sa.Column('entered_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('completed_by', sa.Integer(), nullable=True),
    sa.Column('action_taken', sa.String(length=60), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['completed_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['group_id'], ['workflow_groups.id'], ),
    sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_report_step_instances_report_state', 'report_step_instances', ['report_id', 'state'])
    op.create_index('ix_report_step_instances_report_node', 'report_step_instances', ['report_id', 'node_id'])

    op.add_column('reports', sa.Column('workflow_diagram_id', sa.Integer(), nullable=True))
    # batch mode: SQLite can't ALTER a table to add a constraint or widen a
    # column after the fact (same pattern as the 9088a57024dd/fc92269c93e6
    # migrations).
    with op.batch_alter_table('reports') as batch_op:
        batch_op.create_foreign_key('fk_reports_workflow_diagram_id_workflow_diagrams', 'workflow_diagrams', ['workflow_diagram_id'], ['id'])
        batch_op.alter_column('status', existing_type=sa.String(length=20), type_=sa.String(length=60), nullable=False)

    with op.batch_alter_table('report_transitions') as batch_op:
        batch_op.alter_column('from_status', existing_type=sa.String(length=20), type_=sa.String(length=60))
        batch_op.alter_column('to_status', existing_type=sa.String(length=20), type_=sa.String(length=60), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('report_transitions') as batch_op:
        batch_op.alter_column('to_status', existing_type=sa.String(length=60), type_=sa.String(length=20), nullable=False)
        batch_op.alter_column('from_status', existing_type=sa.String(length=60), type_=sa.String(length=20))

    with op.batch_alter_table('reports') as batch_op:
        batch_op.alter_column('status', existing_type=sa.String(length=60), type_=sa.String(length=20), nullable=False)
        batch_op.drop_constraint('fk_reports_workflow_diagram_id_workflow_diagrams', type_='foreignkey')
        batch_op.drop_column('workflow_diagram_id')

    op.drop_index('ix_report_step_instances_report_node', table_name='report_step_instances')
    op.drop_index('ix_report_step_instances_report_state', table_name='report_step_instances')
    op.drop_table('report_step_instances')
    op.drop_table('workflow_diagrams')
    op.drop_table('workflow_group_memberships')
    op.drop_table('workflow_groups')

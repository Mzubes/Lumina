"""Create the v2 schema.

v2 has been a set of SQLAlchemy classes with no tables behind them since it
was written: `init_db()` only ever created `models.Base.metadata`, and
nothing outside the tests had reason to notice. The template API is the
first thing that needs to persist into it, so the tables have to exist.

This creates the WHOLE v2 schema rather than only the three template
tables, for a practical reason: `template_section` and `template_element`
carry foreign keys to `firm`, `brand_kit`, `display_spec` and
`dataset_field`, so a partial create fails on Postgres the moment it tries
to build those constraints. It is safe to create all of it -- the schema is
additive and self-contained, and nothing reads it yet.

It is generated from the metadata rather than transcribed by hand. Twenty-
four tables of hand-written op.create_table, with their check constraints
and indexes, is a large surface for a typo that Alembic would happily apply
and SQLite would happily ignore. The metadata is already the source of
truth and is already exercised by tests/test_schema_v2*.py.

Revision ID: c8f3a1e60b47
Revises: b4e1c9a77d20
"""

from typing import Sequence, Union

from alembic import op

import schema_v2

revision: str = 'c8f3a1e60b47'
down_revision: Union[str, None] = 'b4e1c9a77d20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    schema_v2.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    # Reverses cleanly because nothing in models.py references v2 -- the
    # separation that made the two schemas coexist also makes this safe.
    schema_v2.metadata.drop_all(bind=op.get_bind())

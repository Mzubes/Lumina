"""The semantic layer -- named warehouse shapes, and how they're displayed.

This replaces the typed fact tables an earlier draft of v2 carried
(Position, Transaction, Valuation, CashFlow, PerformanceReturn,
CompositeReturn, BenchmarkReturn, FxRate). Those were the wrong shape: a
column for `unrealised_gain_loss` or `base_cost_basis` only earns its place
if something computes with it, and Lumina computes nothing. All they bought
was a migration every time a firm wanted a column displayed that the schema
had not anticipated.

What Lumina actually needs is the opposite: take whatever the warehouse
delivers, and give people enormous freedom in how it is grouped, sorted,
filtered and formatted on the page.

    Dataset       a named, queryable shape from the warehouse
                  ("Holdings", "Monthly Returns", "Sector Exposure")
    DatasetField  one column, with the display metadata that makes it
                  presentable -- label, type, number format, whether it is
                  a dimension you group by or a measure you total
    DisplaySpec   a saved grouping / sorting / filtering / subtotal recipe,
                  reusable across templates
    DatasetRow    an optional cache of rows, for screens that cannot afford
                  a warehouse round trip

**Where the line sits.** Lumina aggregates for *display* -- summing
delivered market values into a sector total, counting holdings, taking a
min or max. It does not derive financial metrics. A return, a contribution,
an attribution effect, a cost basis: those carry methodology, and they must
arrive already computed. `AGGREGATIONS` below is deliberately limited to
the display kind, and DatasetField.is_precomputed marks the measures that
must never be re-aggregated -- averaging a column of returns is arithmetic
that produces a number nobody can defend.
"""

from sqlalchemy import (
    CheckConstraint, Column, Date, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint,
)

from .base import Base, FactMixin, TimestampMixin, firm_column
from .structures import _in

# What a dataset's rows are keyed by. Drives which dimension FKs on
# DatasetRow are populated, and which entity a template component binds to.
GRAINS = (
    'portfolio_position',    # one row per instrument held, per date
    'portfolio_period',      # one row per portfolio per period (returns, NAV)
    'composite_period',
    'benchmark_period',
    'portfolio_transaction',
    'client_period',
    'reference',             # no date grain -- a lookup list
)

# A column's job on the page.
#   dimension -- something you group, sort or filter by (sector, country)
#   measure   -- something you total or chart (market value, weight)
#   key       -- an identifier, usually hidden but needed to join or link
FIELD_ROLES = ('dimension', 'measure', 'key')

# How a value is rendered. Format details live in DatasetField.format_spec.
DATA_TYPES = ('string', 'number', 'percent', 'currency', 'date', 'boolean', 'basis_points')

# Display aggregations only -- see the module docstring. Anything requiring
# a financial methodology arrives pre-computed from the warehouse.
AGGREGATIONS = ('none', 'sum', 'count', 'count_distinct', 'min', 'max', 'avg')

SORT_DIRECTIONS = ('asc', 'desc')


class Dataset(Base, TimestampMixin):
    """A named shape Lumina can read from the warehouse and put on a page.

    Defined either as an object to select from (`source_object`, the normal
    case -- a curated Snowflake view) or as a statement (`source_statement`,
    for shapes the warehouse doesn't expose as a view).

    Deliberately not a table of rows. A dataset is a *definition*; rows are
    read live for editing and preview, and frozen into the report snapshot
    at approval. DatasetRow below is a cache, not the source of truth.
    """

    __tablename__ = 'dataset'
    __table_args__ = (
        UniqueConstraint('firm_id', 'code', name='uq_dataset_firm_code'),
        CheckConstraint(_in('grain', GRAINS), name='ck_dataset_grain'),
        # A dataset has to come from somewhere, and naming both an object and
        # a statement leaves it ambiguous which one runs.
        CheckConstraint(
            '(source_object IS NOT NULL AND source_statement IS NULL) '
            'OR (source_object IS NULL AND source_statement IS NOT NULL)',
            name='ck_dataset_one_source',
        ),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    source_id = Column(Integer, ForeignKey('data_source.id'), nullable=False, index=True)

    name = Column(String(200), nullable=False)       # "Holdings"
    code = Column(String(80), nullable=False)        # "holdings"
    description = Column(Text, nullable=True)
    grain = Column(String(40), nullable=False)

    source_object = Column(String(300), nullable=True)     # REPORTING.V_HOLDINGS
    source_statement = Column(Text, nullable=True)

    # Cache rows locally rather than reading live. Worth it for the shapes
    # ops screens hit on every page load; wasteful for a dataset only a
    # quarterly pack reads.
    is_cached = Column(Integer, nullable=False, default=0)
    is_active = Column(Integer, nullable=False, default=1)


class DatasetField(Base, TimestampMixin):
    """One column of a dataset, plus everything needed to present it well.

    This is where marketing quality is won or lost. A number rendered as
    `0.0691` when it should read `+6.91%`, a column header reading
    `MKT_VAL_BASE`, a negative shown as `-1,234` where the house style is
    `(1,234)` -- none of that is a data problem, and all of it is the
    difference between a client-ready page and a database dump.
    """

    __tablename__ = 'dataset_field'
    __table_args__ = (
        UniqueConstraint('dataset_id', 'source_column', name='uq_dataset_field_column'),
        CheckConstraint(_in('field_role', FIELD_ROLES), name='ck_dataset_field_role'),
        CheckConstraint(_in('data_type', DATA_TYPES), name='ck_dataset_field_data_type'),
        CheckConstraint(_in('default_aggregation', AGGREGATIONS), name='ck_dataset_field_aggregation'),
        # A measure that arrived pre-computed must not carry an aggregation:
        # re-aggregating a delivered return is arithmetic nobody can defend.
        CheckConstraint(
            "is_precomputed = 0 OR default_aggregation = 'none'",
            name='ck_dataset_field_precomputed_not_aggregated',
        ),
        Index('ix_dataset_field_dataset', 'dataset_id', 'display_order'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    dataset_id = Column(Integer, ForeignKey('dataset.id'), nullable=False)

    source_column = Column(String(200), nullable=False)   # MKT_VAL_BASE
    name = Column(String(200), nullable=False)            # "Market Value"
    # Shown in a column header when the full label is too wide. Falls back
    # to `name` when unset rather than truncating mid-word.
    short_name = Column(String(80), nullable=True)

    field_role = Column(String(20), nullable=False, default='dimension')
    data_type = Column(String(20), nullable=False, default='string')
    default_aggregation = Column(String(20), nullable=False, default='none')
    # True for anything carrying a methodology: returns, contributions,
    # attribution effects, yields. Enforced above to be non-aggregatable.
    is_precomputed = Column(Integer, nullable=False, default=0)

    # Rendering. JSON text: decimals, thousands separator, percent sign,
    # currency code, negative style (minus vs parentheses vs red), scale
    # (units/thousands/millions), null placeholder. Held as JSON rather than
    # a dozen columns because the set genuinely differs per data type and
    # grows with house style.
    format_spec = Column(Text, nullable=True)
    # left | right | center. Numbers right-align by convention; a column
    # that ignores it reads as amateur.
    alignment = Column(String(10), nullable=True)
    display_order = Column(Integer, nullable=False, default=0)
    is_visible_by_default = Column(Integer, nullable=False, default=1)


class DisplaySpec(Base, TimestampMixin):
    """A saved way of showing a dataset -- group, sort, filter, subtotal, cap.

    The flexibility requirement made reusable. "Top 10 holdings by weight",
    "Holdings grouped by sector, subtotalled, sectors ordered by size", "All
    positions over 1%, sorted by country then name" are three specs over one
    dataset, each nameable and attachable to any template component.

    The four JSON columns are lists of field references plus options rather
    than columns of their own, because their arity is open: a spec may group
    by nothing or by three levels, and a fixed `group_by_1..3` would be both
    limiting and mostly null.
    """

    __tablename__ = 'display_spec'
    __table_args__ = (
        UniqueConstraint('firm_id', 'dataset_id', 'code', name='uq_display_spec_code'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    dataset_id = Column(Integer, ForeignKey('dataset.id'), nullable=False, index=True)

    name = Column(String(200), nullable=False)
    code = Column(String(80), nullable=False)

    # [{"field_id": 12, "sort": "desc", "show_subtotal": true}, ...]
    group_by = Column(Text, nullable=True)
    # [{"field_id": 8, "direction": "desc"}, ...] -- applied within groups
    sort_by = Column(Text, nullable=True)
    # [{"field_id": 8, "op": "gte", "value": 1.0}, ...]
    filters = Column(Text, nullable=True)
    # Which measures to total, and where. {"grand_total": true, "fields": [8]}
    totals = Column(Text, nullable=True)

    # Top-N. `row_limit` caps rows; `remainder_label` names the folded rest
    # ("Other 43 holdings") so a truncated table says it is truncated rather
    # than silently dropping the tail.
    row_limit = Column(Integer, nullable=True)
    remainder_label = Column(String(120), nullable=True)

    is_shared = Column(Integer, nullable=False, default=1)
    created_by_user_id = Column(Integer, nullable=True)


class DatasetRow(Base, FactMixin):
    """A cached row of a dataset.

    A star-schema fact row: dimension foreign keys for the things worth
    grouping and filtering on in SQL, and `values` JSON for everything else.
    That combination is the whole point -- a firm adds a column to its
    warehouse view and it is displayable immediately, with no migration,
    while sector/country/portfolio grouping still runs as an indexed query
    rather than a JSON scan.

    Which dimension keys are populated depends on the dataset's grain; they
    are nullable because a benchmark-period row has no portfolio and a
    reference row has neither.

    Not the source of truth. The warehouse is, and the frozen
    ReportSnapshot is the record of what a client was sent. This table
    exists so an ops dashboard does not bill a warehouse query per page view.
    """

    __tablename__ = 'dataset_row'
    __table_args__ = (
        Index('ix_dataset_row_lookup', 'firm_id', 'dataset_id', 'as_of_date'),
        Index('ix_dataset_row_portfolio', 'portfolio_id', 'as_of_date'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    dataset_id = Column(Integer, ForeignKey('dataset.id'), nullable=False, index=True)

    # Dimension keys, populated per the dataset's grain.
    portfolio_id = Column(Integer, ForeignKey('portfolio.id'), nullable=True, index=True)
    composite_id = Column(Integer, ForeignKey('composite.id'), nullable=True, index=True)
    benchmark_id = Column(Integer, ForeignKey('benchmark.id'), nullable=True, index=True)
    client_id = Column(Integer, ForeignKey('client.id'), nullable=True, index=True)
    instrument_id = Column(Integer, ForeignKey('instrument.id'), nullable=True, index=True)

    # Period-grain rows carry a start; position-grain rows use as_of_date
    # alone (inherited from FactMixin).
    period_start = Column(Date, nullable=True)

    # {"MKT_VAL_BASE": 48000000, "SECTOR": "Technology", "WEIGHT_PCT": 7.8}
    # JSON text here for SQLite parity in dev; JSONB with a GIN index in
    # Postgres, which is what makes filtering on an unmodelled column fast.
    values = Column(Text, nullable=False)

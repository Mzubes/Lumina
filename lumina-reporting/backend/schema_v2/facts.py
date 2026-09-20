"""The facts -- every observed number Lumina reports on.

All of them share FactMixin: an `as_of_date` (the business date described)
and a `data_load_id` (the delivery that carried it, and through it the book,
the source, and the reconciliation attestation). All of them are append-only.

Two things this module deliberately does NOT do:

  - It does not derive positions from transactions. Reconciliation and
    accounting happen upstream; Lumina takes both as given. Transactions are
    here because a client report shows activity and because cost basis and
    realised gain/loss are unanswerable without them -- not because Lumina
    computes a book of record from them.

  - It does not reconcile Valuation.total_market_value against the sum of
    its Positions. Both numbers are recorded as delivered; the stated NAV is
    authoritative because it is the one the administrator struck. A variance
    between them is a signal Lumina can surface, never one it resolves.
"""

from sqlalchemy import (
    CheckConstraint, Column, Date, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint,
)

from .base import (
    PERIOD_TYPES, RETURN_BASES, RETURN_METHODS, TRANSACTION_TYPES,
    Base, FactMixin, firm_column, money_column, percent_column, quantity_column,
)
from .structures import _in


class Position(Base, FactMixin):
    """A holding of one instrument in one portfolio on one date.

    Note what is NOT nullable: `portfolio_id`. Today's equivalent has two
    nullable scope columns and a rule that one must be set; here there is one
    axis and it is always populated. A fund's own positions and a client's
    positions are the same shape, because a fund is a portfolio.

    Amounts are carried in both the instrument's local currency and the
    portfolio's base currency. Storing the translation rather than
    recomputing it means a report rendered today and the same report
    re-rendered next year agree, even though the FX rate moved.
    """

    __tablename__ = 'position'
    __table_args__ = (
        # One row per instrument per portfolio per date per load. The load is
        # part of the key so a restatement can sit alongside the original
        # rather than overwrite it.
        UniqueConstraint('portfolio_id', 'instrument_id', 'as_of_date', 'data_load_id',
                         name='uq_position_portfolio_instrument_date_load'),
        Index('ix_position_lookup', 'firm_id', 'portfolio_id', 'as_of_date'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    portfolio_id = Column(Integer, ForeignKey('portfolio.id'), nullable=False, index=True)
    instrument_id = Column(Integer, ForeignKey('instrument.id'), nullable=False, index=True)
    # Which custodial account this came from, when the feed says. Provenance
    # only -- the reporting unit is always the portfolio.
    custodial_account_id = Column(Integer, ForeignKey('custodial_account.id'), nullable=True)

    quantity = quantity_column(nullable=True)
    local_currency = Column(String(3), nullable=True)
    local_market_value = money_column(nullable=True)
    base_market_value = money_column(nullable=False)
    # Cost is nullable because an IBOR feed often has no cost basis; it comes
    # from the ABOR. A null here means "not supplied", not "zero".
    base_cost_basis = money_column(nullable=True)
    unrealised_gain_loss = money_column(nullable=True)
    accrued_income = money_column(nullable=True)
    # Weight as delivered, not recomputed. The source's own denominator may
    # differ from a naive sum (it may net derivatives, or exclude cash), and
    # second-guessing it produces weights that don't tie to the client's
    # other statements.
    weight_pct = percent_column(nullable=True)
    price = money_column(nullable=True)


class Transaction(Base, FactMixin):
    """One economic event in a portfolio.

    `as_of_date` is the trade date (inherited from FactMixin, where it means
    "the business date this fact describes"); `settlement_date` is separate
    because IBOR and ABOR views differ precisely on which of the two they key
    off.
    """

    __tablename__ = 'transaction'
    __table_args__ = (
        CheckConstraint(_in('transaction_type', TRANSACTION_TYPES), name='ck_transaction_type'),
        UniqueConstraint('firm_id', 'external_id', 'data_load_id', name='uq_transaction_external_id'),
        Index('ix_transaction_lookup', 'firm_id', 'portfolio_id', 'as_of_date'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    portfolio_id = Column(Integer, ForeignKey('portfolio.id'), nullable=False, index=True)
    # Null for portfolio-level events with no instrument -- a management fee,
    # a cash contribution.
    instrument_id = Column(Integer, ForeignKey('instrument.id'), nullable=True, index=True)
    custodial_account_id = Column(Integer, ForeignKey('custodial_account.id'), nullable=True)

    # The sending system's own id, so a redelivery can be matched rather than
    # duplicated.
    external_id = Column(String(120), nullable=True)
    transaction_type = Column(String(30), nullable=False)
    # The firm's own richer transaction code, preserved verbatim. The coarse
    # type above is what calculations branch on; this is what an operations
    # person recognises.
    source_type = Column(String(60), nullable=True)

    settlement_date = Column(Date, nullable=True)
    quantity = quantity_column(nullable=True)
    price = money_column(nullable=True)
    local_currency = Column(String(3), nullable=True)
    local_amount = money_column(nullable=True)
    base_amount = money_column(nullable=False)
    fees = money_column(nullable=True)
    taxes = money_column(nullable=True)
    description = Column(Text, nullable=True)


class Valuation(Base, FactMixin):
    """Portfolio-level totals on a date -- the stated NAV, not a derived sum.

    Kept separate from Position because the official number is struck by the
    administrator and is authoritative even when it differs from the sum of
    the positions delivered alongside it. Deriving the total instead would
    quietly replace the client's official NAV with Lumina's arithmetic.
    """

    __tablename__ = 'valuation'
    __table_args__ = (
        UniqueConstraint('portfolio_id', 'as_of_date', 'data_load_id',
                         name='uq_valuation_portfolio_date_load'),
        Index('ix_valuation_lookup', 'firm_id', 'portfolio_id', 'as_of_date'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    portfolio_id = Column(Integer, ForeignKey('portfolio.id'), nullable=False, index=True)
    # Set for a fund valuation struck per share class.
    share_class_id = Column(Integer, ForeignKey('share_class.id'), nullable=True, index=True)

    base_currency = Column(String(3), nullable=False)
    # Gross of liabilities.
    total_market_value = money_column(nullable=False)
    # Net assets after liabilities -- the NAV proper. Nullable because a
    # position-only feed may not carry it.
    net_asset_value = money_column(nullable=True)
    cash_balance = money_column(nullable=True)
    accrued_income = money_column(nullable=True)
    # Fund share classes only.
    units_outstanding = quantity_column(nullable=True)
    nav_per_unit = money_column(nullable=True)


class CashFlow(Base, FactMixin):
    """An external flow into or out of a portfolio.

    Separate from Transaction even though every flow is also a transaction:
    return calculations need the flows specifically, dated and signed, and
    filtering the full transaction table by type on every performance query
    both costs more and depends on the type mapping staying correct forever.

    `is_large` matters because GIPS requires disclosure of the policy for
    large flows, and firms commonly revalue or temporarily remove a portfolio
    from a composite when one occurs.
    """

    __tablename__ = 'cash_flow'
    __table_args__ = (
        Index('ix_cash_flow_lookup', 'firm_id', 'portfolio_id', 'as_of_date'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    portfolio_id = Column(Integer, ForeignKey('portfolio.id'), nullable=False, index=True)

    # Positive in, negative out. One signed column rather than a direction
    # flag plus a magnitude, so nothing can sum wrongly by ignoring the flag.
    base_amount = money_column(nullable=False)
    local_currency = Column(String(3), nullable=True)
    local_amount = money_column(nullable=True)
    flow_type = Column(String(40), nullable=True)   # contribution, withdrawal, transfer...
    is_large = Column(Integer, nullable=False, default=0)


class PerformanceReturn(Base, FactMixin):
    """A return for one portfolio over one period.

    Returns are taken as delivered, not computed here. The firm's performance
    system owns the methodology, the flow timing and the large-flow policy,
    and a second implementation in a reporting tool would eventually disagree
    with the one the client was already sent.

    `method` and `return_basis` are per-row rather than global because one
    client pack legitimately shows several: TWR for manager skill, MWR for
    the client's own experience, gross and net side by side. Labelling one as
    another is a compliance problem, not a display bug.
    """

    __tablename__ = 'performance_return'
    __table_args__ = (
        CheckConstraint(_in('period_type', PERIOD_TYPES), name='ck_performance_period_type'),
        CheckConstraint(_in('method', RETURN_METHODS), name='ck_performance_method'),
        CheckConstraint(_in('return_basis', RETURN_BASES), name='ck_performance_basis'),
        UniqueConstraint('portfolio_id', 'as_of_date', 'period_type', 'method',
                         'return_basis', 'data_load_id',
                         name='uq_performance_return_key'),
        Index('ix_performance_return_lookup', 'firm_id', 'portfolio_id', 'as_of_date'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    portfolio_id = Column(Integer, ForeignKey('portfolio.id'), nullable=False, index=True)
    share_class_id = Column(Integer, ForeignKey('share_class.id'), nullable=True, index=True)

    period_type = Column(String(10), nullable=False)
    period_start = Column(Date, nullable=True)   # required when period_type is CUSTOM
    method = Column(String(10), nullable=False, default='twr')
    return_basis = Column(String(10), nullable=False, default='gross')
    return_pct = percent_column(nullable=False)
    # Annualised where the period exceeds a year. Null for shorter periods
    # rather than equal to return_pct, so nothing can annualise twice.
    annualised_pct = percent_column(nullable=True)
    currency = Column(String(3), nullable=True)


class CompositeReturn(Base, FactMixin):
    """A return for one composite over one period.

    Its own table rather than a nullable composite_id on PerformanceReturn.
    A composite return is a different object: computed as an asset-weighted
    average of members, and carrying GIPS-required statistics a single
    portfolio has no equivalent of. Keeping them apart means both tables have
    NOT NULL subjects and neither needs an XOR rule.
    """

    __tablename__ = 'composite_return'
    __table_args__ = (
        CheckConstraint(_in('period_type', PERIOD_TYPES), name='ck_composite_period_type'),
        CheckConstraint(_in('method', RETURN_METHODS), name='ck_composite_method'),
        CheckConstraint(_in('return_basis', RETURN_BASES), name='ck_composite_basis'),
        UniqueConstraint('composite_id', 'as_of_date', 'period_type', 'method',
                         'return_basis', 'data_load_id',
                         name='uq_composite_return_key'),
        Index('ix_composite_return_lookup', 'firm_id', 'composite_id', 'as_of_date'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    composite_id = Column(Integer, ForeignKey('composite.id'), nullable=False, index=True)

    period_type = Column(String(10), nullable=False)
    period_start = Column(Date, nullable=True)
    method = Column(String(10), nullable=False, default='twr')
    return_basis = Column(String(10), nullable=False, default='gross')
    return_pct = percent_column(nullable=False)
    annualised_pct = percent_column(nullable=True)
    currency = Column(String(3), nullable=True)

    # --- GIPS-required composite statistics ------------------------------
    # A composite presentation must disclose these; without columns for them
    # they end up typed into a template by hand, which is how they go stale.
    portfolio_count = Column(Integer, nullable=True)
    composite_assets = money_column(nullable=True)
    firm_assets = money_column(nullable=True)
    # Internal dispersion across member portfolios for the period.
    dispersion_pct = percent_column(nullable=True)
    three_year_std_dev_pct = percent_column(nullable=True)
    benchmark_three_year_std_dev_pct = percent_column(nullable=True)


class BenchmarkReturn(Base, FactMixin):
    """A return for one benchmark over one period.

    Its own table for the same reason as CompositeReturn: a clean NOT NULL
    subject beats a nullable-FK union. It also means a benchmark series is
    loaded once and reused by every portfolio measured against it, rather
    than being re-delivered per portfolio as today's single column forces.
    """

    __tablename__ = 'benchmark_return'
    __table_args__ = (
        CheckConstraint(_in('period_type', PERIOD_TYPES), name='ck_benchmark_period_type'),
        UniqueConstraint('benchmark_id', 'as_of_date', 'period_type', 'currency', 'data_load_id',
                         name='uq_benchmark_return_key'),
        Index('ix_benchmark_return_lookup', 'firm_id', 'benchmark_id', 'as_of_date'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    benchmark_id = Column(Integer, ForeignKey('benchmark.id'), nullable=False, index=True)

    period_type = Column(String(10), nullable=False)
    period_start = Column(Date, nullable=True)
    return_pct = percent_column(nullable=False)
    annualised_pct = percent_column(nullable=True)
    currency = Column(String(3), nullable=True)


class FxRate(Base, FactMixin):
    """One currency pair on one date.

    Needed so a report can be presented in a currency other than the
    portfolio's base, and stored as a fact so a historical report translates
    at the rate that was used then rather than today's.
    """

    __tablename__ = 'fx_rate'
    __table_args__ = (
        UniqueConstraint('firm_id', 'from_currency', 'to_currency', 'as_of_date', 'data_load_id',
                         name='uq_fx_rate_key'),
        Index('ix_fx_rate_lookup', 'firm_id', 'as_of_date'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    from_currency = Column(String(3), nullable=False)
    to_currency = Column(String(3), nullable=False)
    rate = quantity_column(nullable=False)

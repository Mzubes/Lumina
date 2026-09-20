"""Benchmarks as entities.

Today a benchmark is a bare Numeric on the performance row -- a return with
no name. A client report that says "+6.9% vs +8.1% bench" without naming the
index is not something you can put in front of an institutional client, and
GIPS requires a benchmark be unambiguous and specified in advance.

Three tables, because benchmarks are genuinely three things:
  Benchmark          the index or blend itself
  BenchmarkComponent the constituents of a blend, weighted
  PortfolioBenchmark which benchmark a portfolio is measured against, and
                     from when -- mandates change benchmarks, and a report
                     covering 2024 must use the 2024 benchmark
"""

from sqlalchemy import (
    CheckConstraint, Column, Date, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint,
)

from .base import Base, TimestampMixin, firm_column, percent_column


class Benchmark(Base, TimestampMixin):
    """A named index, or a blend of them."""

    __tablename__ = 'benchmark'
    __table_args__ = (UniqueConstraint('firm_id', 'code', name='uq_benchmark_firm_code'),)

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()

    name = Column(String(250), nullable=False)      # "MSCI ACWI ex-USA Small Cap Value (Net)"
    code = Column(String(60), nullable=False)
    provider = Column(String(120), nullable=True)   # MSCI, FTSE Russell, Bloomberg...
    currency = Column(String(3), nullable=True)
    # Net vs gross of withholding tax. Comparing a net-of-tax portfolio return
    # to a gross index overstates performance, so the variant is recorded
    # rather than left to the name.
    return_variant = Column(String(20), nullable=True)   # net, gross, total, price
    # True when this is a weighted blend -- its parts live in
    # BenchmarkComponent and its returns are computed, not fed in.
    is_blend = Column(Integer, nullable=False, default=0)
    description = Column(Text, nullable=True)


class BenchmarkComponent(Base, TimestampMixin):
    """One weighted leg of a blended benchmark, effective-dated.

    "60% ACWI / 40% Agg" is two rows. The weights are dated because a blend's
    weights are re-struck periodically, and a historical report has to use the
    weights that were in force then.
    """

    __tablename__ = 'benchmark_component'
    __table_args__ = (
        Index('ix_benchmark_component_parent', 'benchmark_id', 'effective_from'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    benchmark_id = Column(Integer, ForeignKey('benchmark.id'), nullable=False)
    component_benchmark_id = Column(Integer, ForeignKey('benchmark.id'), nullable=False)

    weight_pct = percent_column(nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)   # null = still in force


class PortfolioBenchmark(Base, TimestampMixin):
    """Which benchmark a portfolio is measured against, and over what period.

    Effective-dated rather than a column on Portfolio, because a mandate's
    benchmark changes and the old reports must not silently re-point at the
    new one.

    `is_primary` exists because portfolios routinely carry a primary benchmark
    plus secondary comparators (a peer group, a cash rate), and a report needs
    to know which one the headline comparison uses.
    """

    __tablename__ = 'portfolio_benchmark'
    __table_args__ = (
        CheckConstraint('is_primary IN (0, 1)', name='ck_portfolio_benchmark_primary'),
        Index('ix_portfolio_benchmark_lookup', 'portfolio_id', 'effective_from'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    portfolio_id = Column(Integer, ForeignKey('portfolio.id'), nullable=False)
    benchmark_id = Column(Integer, ForeignKey('benchmark.id'), nullable=False)

    is_primary = Column(Integer, nullable=False, default=1)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)

"""GIPS composites.

A composite is an aggregation of portfolios managed to a similar mandate; its
return is the asset-weighted average of its members. This is the correct name
for what today's schema approximates with fund-scoped holdings, and naming it
properly brings obligations worth having:

  - every discretionary, fee-paying portfolio must belong to at least one
    composite (checkable, given Portfolio.is_discretionary / is_fee_paying)
  - membership is effective-dated, and a portfolio that leaves stays in for
    the periods it was managed -- a composite's history cannot be rewritten
    by today's client list
"""

from sqlalchemy import (
    Column, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)

from .base import Base, TimestampMixin, firm_column


class Composite(Base, TimestampMixin):
    """A named aggregation of portfolios sharing a mandate."""

    __tablename__ = 'composite'
    __table_args__ = (UniqueConstraint('firm_id', 'code', name='uq_composite_firm_code'),)

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    strategy_id = Column(Integer, ForeignKey('strategy.id'), nullable=True, index=True)

    name = Column(String(250), nullable=False)
    code = Column(String(60), nullable=False)
    # The written composite definition -- the criteria for inclusion. GIPS
    # requires it to exist and be available on request, so it lives with the
    # composite rather than in a document nobody can locate.
    definition = Column(Text, nullable=True)
    base_currency = Column(String(3), nullable=False, default='USD')
    creation_date = Column(Date, nullable=True)     # when the composite was defined
    inception_date = Column(Date, nullable=True)    # when its track record starts
    terminated_date = Column(Date, nullable=True)
    # A minimum size below which portfolios are excluded, if the firm sets
    # one. GIPS requires disclosing it, which means storing it.
    minimum_asset_level = Column(String(40), nullable=True)


class CompositeMembership(Base, TimestampMixin):
    """A portfolio's membership of a composite, over a period.

    Rows are added and closed, never deleted. Deleting a membership would
    erase a period from the composite's track record, which is precisely what
    GIPS exists to prevent.
    """

    __tablename__ = 'composite_membership'
    __table_args__ = (
        Index('ix_composite_membership_lookup', 'composite_id', 'effective_from'),
        Index('ix_composite_membership_portfolio', 'portfolio_id'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    composite_id = Column(Integer, ForeignKey('composite.id'), nullable=False)
    portfolio_id = Column(Integer, ForeignKey('portfolio.id'), nullable=False)

    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    # Why it joined or left. Auditors ask; "the client terminated" and "we
    # decided it no longer fits the mandate" are very different answers.
    inclusion_reason = Column(String(250), nullable=True)
    exclusion_reason = Column(String(250), nullable=True)

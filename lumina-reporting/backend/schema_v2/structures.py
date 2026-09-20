"""Portfolio -- the centre of the whole schema.

This module carries the single most important decision in v2:

    **Every pool of assets is a Portfolio, including funds.**

Today's schema has two parallel axes -- `client_id` and `fund_id`, both
nullable on every fact table -- and the "level" of a row is implied by which
one is populated. That is why a client cannot hold two mandates in the same
strategy, why client-level AUM silently reads zero when the feed is
fund-scoped, and why every query that touches holdings has to branch.

Here there is one axis. A separate account is a portfolio. A commingled fund
is a portfolio. A model is a portfolio. Positions, valuations, transactions
and returns all hang off `portfolio_id`, NOT NULL, always.

A client's economic interest in a pooled fund is not a special case either:
it is an ordinary Position in the client's own portfolio whose instrument
happens to be that fund's share class. That is what actually happens
economically, and modelling it that way means the fund look-through is a
join rather than a rule.
"""

from sqlalchemy import (
    CheckConstraint, Column, Date, ForeignKey, Index, Integer, Numeric, String, Text,
    UniqueConstraint,
)

from .base import PORTFOLIO_TYPES, Base, TimestampMixin, firm_column


def _in(column, values):
    """A CheckConstraint restricting `column` to `values`, rendered as SQL."""
    rendered = ', '.join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


class Strategy(Base, TimestampMixin):
    """An investment approach -- "Global Small Cap Focused Value".

    What today's FundData was reaching for, minus the conflation with a
    vehicle. A strategy is an idea; the money implementing it lives in
    portfolios, which is why AUM, positions and returns are not on this table.
    """

    __tablename__ = 'strategy'
    __table_args__ = (UniqueConstraint('firm_id', 'code', name='uq_strategy_firm_code'),)

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()

    name = Column(String(200), nullable=False)
    code = Column(String(50), nullable=False)
    asset_class = Column(String(80), nullable=True)
    investment_universe = Column(String(200), nullable=True)
    inception_date = Column(Date, nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Integer, nullable=False, default=1)


class Portfolio(Base, TimestampMixin):
    """A discrete pool of assets with its own positions, returns and reports.

    `portfolio_type` distinguishes the three shapes without splitting them
    into three tables, because everything downstream treats them identically:
    they all hold positions, they all have a NAV, they all produce returns.

    `is_discretionary` and `is_fee_paying` are not decoration. GIPS requires
    every discretionary, fee-paying portfolio to be in at least one composite,
    so a composite completeness check is impossible without them -- and that
    check is exactly the kind of thing a verifier asks for.
    """

    __tablename__ = 'portfolio'
    __table_args__ = (
        UniqueConstraint('firm_id', 'code', name='uq_portfolio_firm_code'),
        CheckConstraint(_in('portfolio_type', PORTFOLIO_TYPES), name='ck_portfolio_type'),
        # A separate account belongs to exactly one client; a pooled fund or
        # model belongs to none. Enforcing it here stops the "whose money is
        # this?" ambiguity that today's nullable pair creates.
        CheckConstraint(
            "(portfolio_type = 'separate_account' AND client_id IS NOT NULL) "
            "OR (portfolio_type <> 'separate_account' AND client_id IS NULL)",
            name='ck_portfolio_client_matches_type',
        ),
        Index('ix_portfolio_firm_client', 'firm_id', 'client_id'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()

    name = Column(String(200), nullable=False)
    # The firm's own identifier for this portfolio. The join key for inbound
    # position and transaction feeds.
    code = Column(String(80), nullable=False)
    portfolio_type = Column(String(30), nullable=False)

    client_id = Column(Integer, ForeignKey('client.id'), nullable=True, index=True)
    strategy_id = Column(Integer, ForeignKey('strategy.id'), nullable=True, index=True)

    # Every number on this portfolio is denominated here. A client reporting
    # in a different currency is handled by translating at report time via
    # fx_rate, not by storing the same position twice.
    base_currency = Column(String(3), nullable=False, default='USD')

    inception_date = Column(Date, nullable=True)
    # Set rather than deleted. A terminated portfolio's history still has to
    # render -- prior reports reference it, and GIPS requires terminated
    # portfolios stay in their composites for the periods they were managed.
    terminated_date = Column(Date, nullable=True)

    is_discretionary = Column(Integer, nullable=False, default=1)
    is_fee_paying = Column(Integer, nullable=False, default=1)

    # Fund-only. Null on a separate account or model.
    legal_structure = Column(String(80), nullable=True)   # UCITS, SICAV, LP, CIT...
    domicile_country = Column(String(2), nullable=True)


class ShareClass(Base, TimestampMixin):
    """A share class of a pooled fund.

    Lives on the fund side, which is where the industry puts it and where
    subscriptions and redemptions actually happen. Each share class is also
    an Instrument (see `instrument_id`), which is what lets a client's holding
    of the fund be an ordinary position rather than a special case.
    """

    __tablename__ = 'share_class'
    __table_args__ = (
        UniqueConstraint('portfolio_id', 'code', name='uq_share_class_portfolio_code'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    # The pooled_fund portfolio this class is a slice of.
    portfolio_id = Column(Integer, ForeignKey('portfolio.id'), nullable=False, index=True)
    # The tradeable instrument representing this class. Nullable only during
    # onboarding, before the security master has the row.
    instrument_id = Column(Integer, ForeignKey('instrument.id'), nullable=True, index=True)

    name = Column(String(200), nullable=False)
    code = Column(String(50), nullable=False)          # "I USD Acc"
    currency = Column(String(3), nullable=False, default='USD')
    is_hedged = Column(Integer, nullable=False, default=0)
    is_distributing = Column(Integer, nullable=False, default=0)
    management_fee_bps = Column(Numeric(8, 2), nullable=True)
    minimum_investment = Column(Numeric(20, 2), nullable=True)
    launch_date = Column(Date, nullable=True)
    closed_date = Column(Date, nullable=True)


class CustodialAccount(Base, TimestampMixin):
    """An account at a custodian, as the custodian knows it.

    Separate from Portfolio because the two genuinely differ: one portfolio
    may span several custodial accounts (a cash account plus a securities
    account, or one per jurisdiction), and the reporting unit the client
    cares about is the portfolio, not the plumbing.

    This is also the level at which upstream reconciliation happens. Lumina
    stores the account so a position can say which custodian's books it came
    from -- it does not reconcile against it.
    """

    __tablename__ = 'custodial_account'
    __table_args__ = (
        UniqueConstraint('firm_id', 'custodian_name', 'account_number',
                         name='uq_custodial_account_number'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    portfolio_id = Column(Integer, ForeignKey('portfolio.id'), nullable=False, index=True)

    custodian_name = Column(String(200), nullable=False)
    account_number = Column(String(100), nullable=False)
    account_name = Column(String(200), nullable=True)
    base_currency = Column(String(3), nullable=True)
    opened_date = Column(Date, nullable=True)
    closed_date = Column(Date, nullable=True)

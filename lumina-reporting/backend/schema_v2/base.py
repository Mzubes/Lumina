"""Shared declarative base, column conventions and vocabularies for v2.

Deliberately a separate Base from models.py's. The two schemas coexist during
cutover, and sharing one metadata would mean `create_all()` on either brings
up both.
"""

import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()
metadata = Base.metadata

# ---------------------------------------------------------------------------
# Vocabularies
#
# Held as Python tuples and applied as CheckConstraints rather than native
# ENUM types: SQLite (dev/test here) has no ENUM, and altering a Postgres ENUM
# is a migration-time lock. A check constraint says the same thing and is
# cheap to widen.
# ---------------------------------------------------------------------------

# What kind of pool of assets a portfolio is.
#   separate_account -- one client's own money, managed to a strategy (an SMA)
#   pooled_fund      -- a commingled vehicle; clients own units of it, not of
#                       its underlying positions
#   model            -- a model portfolio carrying no real money, used as the
#                       template a strategy is expressed in
PORTFOLIO_TYPES = ('separate_account', 'pooled_fund', 'model')

# Which book of record a fact came from. The distinction matters because the
# same portfolio on the same date has legitimately different positions in each
# -- an IBOR reflects trade-date intent, an ABOR reflects settled accounting.
# A client asking "does this tie to my custodian?" is asking which book this
# number is from, so the answer has to be recorded rather than assumed.
BOOKS = ('ibor', 'abor', 'custodian', 'manual')

# What a data load carries. One load is one (source, domain, as-of) delivery.
DATA_DOMAINS = ('position', 'transaction', 'valuation', 'cash_flow',
                'performance', 'benchmark', 'fx', 'reference')

# Reconciliation happens UPSTREAM of Lumina. These values record what the
# upstream system asserted, not anything Lumina computed.
#   reconciled   -- the sending system attests this load ties out
#   unreconciled -- it does not, or said nothing; not publishable
#   waived       -- a human accepted it anyway, with a recorded reason
RECONCILIATION_STATUSES = ('reconciled', 'unreconciled', 'waived')

# Return methodologies. Stored per row rather than assumed globally, because a
# single client report legitimately shows both (TWR for manager skill, MWR for
# the client's own experience) and mislabelling one as the other is a
# compliance problem, not a display bug.
RETURN_METHODS = ('twr', 'mwr', 'simple')

RETURN_BASES = ('gross', 'net')

PERIOD_TYPES = ('DAY', 'MTD', 'QTD', 'YTD', '1Y', '3Y', '5Y', '10Y', 'ITD', 'CUSTOM')

# Economic effect of a transaction. Kept coarse on purpose: a firm's own
# transaction codes are richer and land in `source_type`, while this column is
# the handful of buckets every downstream calculation actually branches on.
TRANSACTION_TYPES = ('buy', 'sell', 'contribution', 'withdrawal', 'income',
                     'expense', 'fee', 'tax', 'transfer_in', 'transfer_out',
                     'corporate_action', 'fx', 'other')

# ---------------------------------------------------------------------------
# Column helpers
# ---------------------------------------------------------------------------

# Money and quantities: Numeric, never Float. Binary floating point cannot
# represent 0.1, and a client report that sums to $1,000,000.00000001 is a
# support ticket.
def money_column(**kwargs):
    return Column(Numeric(20, 4), **kwargs)


def quantity_column(**kwargs):
    return Column(Numeric(24, 8), **kwargs)


# Returns and weights are stored as percentages (7.25 means 7.25%), matching
# how every source system in this domain publishes them and how every report
# displays them. Storing decimals instead would mean a conversion on the way
# in and another on the way out, with two places to get it wrong.
def percent_column(**kwargs):
    return Column(Numeric(12, 6), **kwargs)


def currency_column(**kwargs):
    kwargs.setdefault('nullable', False)
    return Column(String(3), **kwargs)


def firm_column():
    """Every table carries its tenant. This is the column a Postgres
    row-level-security policy keys on, which is why it is NOT NULL everywhere
    and never inferred through a join -- a policy that has to traverse a join
    is a policy that gets bypassed."""
    return Column(Integer, ForeignKey('firm.id'), nullable=False, index=True)


class TimestampMixin:
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)


class FactMixin:
    """Applied to every table that holds an observed number.

    Two rules make facts trustworthy:

    1. `as_of_date` is the business date the fact describes (valid time);
       `data_load_id` points at the delivery that carried it, whose own
       `loaded_at` is when Lumina learned it (transaction time). Together
       they answer "what did we believe on date X about date Y" without the
       weight of a full bitemporal schema.

    2. Facts are append-only. A restatement is a NEW load for the same
       as_of_date that supersedes the prior one -- never an UPDATE. That is
       what makes a distributed report reproducible years later: the rows it
       was rendered from are still exactly as they were.
    """
    as_of_date = Column(Date, nullable=False, index=True)
    data_load_id = Column(Integer, ForeignKey('data_load.id'), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

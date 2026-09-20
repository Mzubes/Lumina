"""Security master.

Today's schema has no instrument table at all -- a holding carries a bare
`security_id` string and a `security_name`, so the same security arriving
from two feeds under two identifiers becomes two unrelated rows that never
aggregate. That is the classic cause of a factsheet whose top-ten holdings
list the same name twice.
"""

from sqlalchemy import (
    Column, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)

from .base import Base, TimestampMixin, firm_column


class Instrument(Base, TimestampMixin):
    """One security, fund unit, or cash balance -- the thing a position is in.

    Cash is an instrument here, not a separate concept. Every downstream
    calculation (weights, asset allocation, totals) then works over one list
    instead of special-casing a cash row that lives somewhere else.
    """

    __tablename__ = 'instrument'
    __table_args__ = (
        UniqueConstraint('firm_id', 'primary_identifier', name='uq_instrument_primary_id'),
        Index('ix_instrument_firm_asset_class', 'firm_id', 'asset_class'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()

    name = Column(String(300), nullable=False)
    # Whichever identifier this firm treats as canonical -- usually the
    # security master's internal id. Alternates live in InstrumentIdentifier.
    primary_identifier = Column(String(100), nullable=False)

    instrument_type = Column(String(50), nullable=True)   # equity, bond, fund_unit, cash, derivative...
    asset_class = Column(String(80), nullable=True)
    sector = Column(String(120), nullable=True)
    industry = Column(String(120), nullable=True)
    country = Column(String(2), nullable=True)
    currency = Column(String(3), nullable=True)
    issuer_name = Column(String(300), nullable=True)

    # Fixed income only.
    maturity_date = Column(Date, nullable=True)
    coupon_rate = Column(String(20), nullable=True)
    credit_rating = Column(String(20), nullable=True)

    is_active = Column(Integer, nullable=False, default=1)
    notes = Column(Text, nullable=True)


class InstrumentIdentifier(Base, TimestampMixin):
    """Alternate identifiers for one instrument.

    A real security carries an ISIN, a CUSIP, a SEDOL, a ticker, a Bloomberg
    id and whatever the custodian calls it. A single column cannot hold that,
    and picking one means every feed keyed on a different one fails to match.
    """

    __tablename__ = 'instrument_identifier'
    __table_args__ = (
        UniqueConstraint('firm_id', 'id_type', 'id_value', name='uq_instrument_identifier'),
        Index('ix_instrument_identifier_instrument', 'instrument_id'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    instrument_id = Column(Integer, ForeignKey('instrument.id'), nullable=False)

    id_type = Column(String(30), nullable=False)   # isin, cusip, sedol, ticker, bloomberg, custodian
    id_value = Column(String(100), nullable=False)
    # Where this identifier came from, so a bad mapping can be traced back to
    # the feed that introduced it.
    source_id = Column(Integer, ForeignKey('data_source.id'), nullable=True)

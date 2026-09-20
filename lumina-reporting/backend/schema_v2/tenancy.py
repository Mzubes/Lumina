"""The tenant boundary.

Today's schema has no firm concept at all -- every row belongs to whoever
happens to be querying. That is fine for one firm and unshippable for two,
and retrofitting a tenant column across two dozen tables later is far more
expensive than carrying it from the start.
"""

from sqlalchemy import Column, Integer, String, Text

from .base import Base, TimestampMixin


class Firm(Base, TimestampMixin):
    """One asset manager. The root of every scope chain in this schema."""

    __tablename__ = 'firm'

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    # Short code used in client-facing references and file names
    # (e.g. "PZN" -> PZN-2026Q3-MERIDIAN.pdf).
    code = Column(String(20), nullable=False, unique=True)
    # The currency the firm reports its own AUM in. Individual portfolios
    # keep their own base currency; this is only for firm-level roll-ups.
    reporting_currency = Column(String(3), nullable=False, default='USD')
    # GIPS firm definition -- the text stating what "the firm" covers for
    # compliance purposes. Required to claim GIPS compliance, and a real
    # thing auditors ask to see, so it has a home rather than living in a
    # policy document nobody can find.
    gips_firm_definition = Column(Text, nullable=True)
    is_active = Column(Integer, nullable=False, default=1)

"""Lumina data model v2.

A ground-up replacement for the flat Client/FundData pair in models.py,
designed around one decision: **Lumina is a reporting system downstream of an
already-reconciled book of record.** It does not reconcile. It records that
reconciliation happened upstream, and refuses to publish numbers that carry
no attestation.

Everything here is additive and self-contained -- its own declarative Base,
its own metadata, its own tables. Nothing in models.py imports it and nothing
here imports models.py, so the two can be created side by side, compared, and
cut over deliberately rather than in one irreversible migration. See
docs/DATA_MODEL_V2.md for the mapping from today's schema and the cutover
sequence.
"""

from .base import Base, metadata  # noqa: F401
from .tenancy import Firm  # noqa: F401
from .parties import Client, ClientGroup, Contact  # noqa: F401
from .structures import CustodialAccount, Portfolio, ShareClass, Strategy  # noqa: F401
from .instruments import Instrument, InstrumentIdentifier  # noqa: F401
from .benchmarks import Benchmark, BenchmarkComponent, PortfolioBenchmark  # noqa: F401
from .composites import Composite, CompositeMembership  # noqa: F401
from .governance import DataLoad, DataSource  # noqa: F401
from .reporting import ReportDataBinding, ReportSnapshot  # noqa: F401
from .facts import (  # noqa: F401
    BenchmarkReturn, CashFlow, CompositeReturn, FxRate, PerformanceReturn,
    Position, Transaction, Valuation,
)

__all__ = [
    'Base', 'metadata',
    'Firm',
    'ClientGroup', 'Client', 'Contact',
    'Strategy', 'Portfolio', 'ShareClass', 'CustodialAccount',
    'Instrument', 'InstrumentIdentifier',
    'Benchmark', 'BenchmarkComponent', 'PortfolioBenchmark',
    'Composite', 'CompositeMembership',
    'DataSource', 'DataLoad',
    'ReportSnapshot', 'ReportDataBinding',
    'Position', 'Transaction', 'Valuation', 'CashFlow',
    'PerformanceReturn', 'CompositeReturn', 'BenchmarkReturn', 'FxRate',
]

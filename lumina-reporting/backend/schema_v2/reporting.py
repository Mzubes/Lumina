"""The frozen payload behind a distributed report.

This module exists because of how Lumina actually sources data: finalized
facts live in the warehouse, and Lumina reads them. That raises a question
the current app answers badly.

Today a generated report stores a rendered PDF at `Report.file_path`, but
the export and preview endpoints call `resolve_report_content()` again,
live. So the PDF a client received is frozen while the preview beside it
re-resolves from whatever the warehouse says now. After any upstream
restatement those two disagree, and nothing in the system says so.

ReportSnapshot fixes that by freezing the resolved content at the moment a
report is approved -- the numbers, not just the rendering. Everything
afterwards (re-render to PDF, XLSX, the web view, the client portal) reads
the snapshot. A report becomes reproducible without Lumina having to
warehouse a permanent copy of every fact it ever read.
"""

from sqlalchemy import (
    Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)

from .base import Base, TimestampMixin, firm_column


class ReportSnapshot(Base, TimestampMixin):
    """The resolved content of one report, frozen at approval.

    `payload` is the same structure `resolve_report_content()` already
    produces -- component-by-component resolved values -- serialized as JSON
    text. Storing the resolved payload rather than the source rows is the
    point: it is small, it is exactly what was shown, and it does not require
    keeping every position row alive forever to reproduce one factsheet.

    `content_hash` makes tampering detectable and makes "is this the same
    pack we sent in March?" a string comparison instead of a diff.
    """

    __tablename__ = 'report_snapshot'
    __table_args__ = (
        # One frozen snapshot per report per version. A corrected reissue is
        # a new version, never an overwrite -- the client already has the old
        # one, so it stays on record.
        UniqueConstraint('report_id', 'version', name='uq_report_snapshot_version'),
        Index('ix_report_snapshot_report', 'firm_id', 'report_id'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    # -> reports.id in the application schema. Deliberately not an FK: the
    # reporting/workflow tables stay in models.py through cutover, and a
    # cross-metadata FK cannot be expressed anyway.
    report_id = Column(Integer, nullable=False)

    version = Column(Integer, nullable=False, default=1)
    as_of_date = Column(DateTime, nullable=False)
    frozen_at = Column(DateTime, nullable=False)
    frozen_by_user_id = Column(Integer, nullable=True)

    payload = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)

    # Presentation currency, when it differs from the portfolio's base and
    # the payload was translated. Recorded so a reader knows the numbers were
    # converted and at which date's rates (the fx load is bound below).
    presentation_currency = Column(String(3), nullable=True)


class ReportDataBinding(Base, TimestampMixin):
    """Which data loads one snapshot was built from.

    The audit answer to "where did this number come from". A pack typically
    binds several: positions, performance, benchmark, and FX if it was
    translated.

    This is also where the reconciliation gate is enforced in practice --
    freezing a snapshot checks `DataLoad.is_publishable` for every load about
    to be bound, and refuses the whole operation if any answers False. One
    unattested load cannot slip into a pack alongside three good ones.
    """

    __tablename__ = 'report_data_binding'
    __table_args__ = (
        UniqueConstraint('report_snapshot_id', 'data_load_id', name='uq_report_data_binding'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    report_snapshot_id = Column(Integer, ForeignKey('report_snapshot.id'), nullable=False, index=True)
    data_load_id = Column(Integer, ForeignKey('data_load.id'), nullable=False, index=True)

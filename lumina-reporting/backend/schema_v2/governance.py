"""Provenance, and the reconciliation contract.

This module is where the central product decision lives:

    **Reconciliation happens upstream, before data reaches Lumina.**

Lumina therefore does not compare positions to custodians, does not compute
breaks, and has no break-resolution workflow. What it does instead is record
the upstream system's attestation and make it a precondition for publishing:
a report cannot be distributed from data that nobody asserted was reconciled.

That turns a process promise into a schema constraint. Without it, "we
reconcile upstream" is a sentence in a runbook; with it, an unreconciled load
physically cannot reach a client.
"""

from sqlalchemy import (
    CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer, String, Text,
)

from .base import (
    BOOKS, DATA_DOMAINS, RECONCILIATION_STATUSES, Base, TimestampMixin, firm_column,
)
from .structures import _in


class DataSource(Base, TimestampMixin):
    """A system Lumina reads from.

    Carried over from today's model with the tenant column added and the
    `last_sync_*` fields removed: per-source sync state was a single mutable
    row that could only describe the most recent run. DataLoad below records
    every run, which is what provenance actually needs.
    """

    __tablename__ = 'data_source'

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()

    name = Column(String(150), nullable=False)
    source_type = Column(String(40), nullable=False)   # snowflake, databricks, api, sftp, manual
    # Connection settings as JSON text. Secrets are stripped on serialize by
    # the route layer, same convention as today's CONFIG_SECRET_KEYS.
    config = Column(Text, nullable=True)
    # Which book this source speaks for. A custodian feed and an IBOR feed
    # disagree legitimately; knowing which is which is the whole point.
    book = Column(String(20), nullable=True)
    is_active = Column(Integer, nullable=False, default=1)


class DataLoad(Base, TimestampMixin):
    """One delivery of one domain of data, for one as-of date.

    Every fact row in this schema points at the load that carried it. That
    single FK is what makes the facts trustworthy:

      - provenance: which system, which book, which run
      - reproducibility: a report pins its loads, so re-rendering it years
        later produces the same numbers even after restatements
      - restatement: a corrected delivery is a NEW load with the same
        as_of_date and `supersedes_id` pointing at the old one. Facts are
        never updated in place, so history stays intact
      - publishability: `reconciliation_status` gates distribution

    `is_current` is denormalised from the supersession chain. It could be
    derived, but every fact query filters on it, and a recursive walk per
    query to establish "is this the live version" is not something to pay for
    on every page load.
    """

    __tablename__ = 'data_load'
    __table_args__ = (
        CheckConstraint(_in('book', BOOKS), name='ck_data_load_book'),
        CheckConstraint(_in('domain', DATA_DOMAINS), name='ck_data_load_domain'),
        CheckConstraint(_in('reconciliation_status', RECONCILIATION_STATUSES),
                        name='ck_data_load_reconciliation_status'),
        # A waiver must say why. An unexplained override of the publishing
        # gate is the one thing that would make the gate meaningless.
        CheckConstraint(
            "reconciliation_status <> 'waived' OR waiver_reason IS NOT NULL",
            name='ck_data_load_waiver_has_reason',
        ),
        Index('ix_data_load_lookup', 'firm_id', 'domain', 'as_of_date', 'is_current'),
    )

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    source_id = Column(Integer, ForeignKey('data_source.id'), nullable=False, index=True)

    domain = Column(String(30), nullable=False)
    book = Column(String(20), nullable=False)
    as_of_date = Column(Date, nullable=False)

    loaded_at = Column(DateTime, nullable=False)
    row_count = Column(Integer, nullable=True)

    # --- the upstream reconciliation attestation -------------------------
    # Lumina asserts none of this itself. These columns record what the
    # sending system said, and who said it.
    reconciliation_status = Column(String(20), nullable=False, default='unreconciled')
    reconciled_at = Column(DateTime, nullable=True)
    # The upstream system and its run identifier, so an auditor can follow
    # the claim back to the system that made it.
    reconciled_by_system = Column(String(150), nullable=True)
    reconciliation_reference = Column(String(200), nullable=True)
    # Only set when status is 'waived'. Who accepted unreconciled data, and
    # on what grounds.
    waiver_reason = Column(Text, nullable=True)
    waived_by_user_id = Column(Integer, nullable=True)  # -> users.id in the app schema

    # --- warehouse provenance --------------------------------------------
    # When the source is a warehouse (Snowflake being the expected one), the
    # exact query and the exact point in time it read are worth keeping.
    # Together they make a load re-runnable rather than merely described:
    # Snowflake's Time Travel can reproduce the same rows from
    # `source_as_of_timestamp` even after the table has since been reloaded,
    # which is the difference between "we think this is what it said" and
    # "here it is again".
    #
    # `source_query_reference` holds the warehouse's own query id; the
    # statement itself lives in `source_statement` when the firm wants the
    # SQL on record for audit. Neither is required -- a manual upload or an
    # SFTP drop has no query.
    source_query_reference = Column(String(200), nullable=True)
    source_as_of_timestamp = Column(DateTime, nullable=True)
    source_statement = Column(Text, nullable=True)

    # --- restatement chain ------------------------------------------------
    supersedes_id = Column(Integer, ForeignKey('data_load.id'), nullable=True)
    is_current = Column(Integer, nullable=False, default=1)

    notes = Column(Text, nullable=True)

    @property
    def is_publishable(self):
        """Whether a client-facing report may be rendered from this load.

        The one rule the upstream-reconciliation decision reduces to. Report
        generation checks every load it intends to read and refuses if any
        answers False.
        """
        return self.reconciliation_status in ('reconciled', 'waived') and bool(self.is_current)

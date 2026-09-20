"""Who the money belongs to.

Three levels, only one of which is new relative to today's schema:

    ClientGroup   optional -- a family office, a pension scheme's several
                  legal entities, a parent and its subsidiaries. Exists so a
                  relationship can be reported on as a whole without
                  pretending the legal entities are one.
    Client        the legal entity that owns portfolios and receives reports.
    Contact       people at the client. Unchanged in spirit from today.

Deliberately NOT here: anything about what the client owns. That is the
portfolio's job. Today's schema hangs holdings directly off Client, which is
what makes two mandates for one client unrepresentable.
"""

from sqlalchemy import Column, Date, ForeignKey, Integer, String, Text, UniqueConstraint

from .base import Base, TimestampMixin, firm_column


class ClientGroup(Base, TimestampMixin):
    """A relationship spanning several legal entities.

    Only one level deep on purpose. A self-referencing tree would let a firm
    build an arbitrarily deep hierarchy, and every query that rolls up would
    then need recursion. Groups of groups have not been asked for; when they
    are, a parent_id here is an additive change.
    """

    __tablename__ = 'client_group'
    __table_args__ = (UniqueConstraint('firm_id', 'name', name='uq_client_group_firm_name'),)

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    name = Column(String(200), nullable=False)
    relationship_manager_id = Column(Integer, nullable=True)  # -> users.id in the app schema
    notes = Column(Text, nullable=True)


class Client(Base, TimestampMixin):
    """A legal entity that owns portfolios and receives reports."""

    __tablename__ = 'client'
    __table_args__ = (UniqueConstraint('firm_id', 'external_id', name='uq_client_firm_external_id'),)

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    client_group_id = Column(Integer, ForeignKey('client_group.id'), nullable=True, index=True)

    name = Column(String(200), nullable=False)
    legal_name = Column(String(300), nullable=True)
    # The id this client carries in the firm's CRM or book of record. The
    # join key for every inbound feed, which is why it is unique per firm
    # rather than merely informational.
    external_id = Column(String(100), nullable=True)

    # Drives which disclosures a report must carry and which regulatory
    # regime applies. Free text rather than an enum: the useful categories
    # differ by jurisdiction and by firm.
    client_type = Column(String(50), nullable=True)   # pension, endowment, insurance, sovereign...
    domicile_country = Column(String(2), nullable=True)  # ISO 3166-1 alpha-2
    reporting_currency = Column(String(3), nullable=True)  # null -> use the portfolio's base

    relationship_manager_id = Column(Integer, nullable=True)  # -> users.id in the app schema
    onboarded_on = Column(Date, nullable=True)
    terminated_on = Column(Date, nullable=True)  # set, never deleted: reports already sent stay valid


class Contact(Base, TimestampMixin):
    """A person at a client. Recipients of distributed reports."""

    __tablename__ = 'contact'

    id = Column(Integer, primary_key=True)
    firm_id = firm_column()
    client_id = Column(Integer, ForeignKey('client.id'), nullable=False, index=True)

    name = Column(String(200), nullable=False)
    email = Column(String(200), nullable=True)
    title = Column(String(150), nullable=True)
    phone = Column(String(40), nullable=True)
    # Whether this contact is on the distribution list by default. A client
    # has many contacts and only some of them should receive every pack.
    receives_reports = Column(Integer, nullable=False, default=1)

import datetime
import json

from sqlalchemy import event
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from werkzeug.security import check_password_hash, generate_password_hash

CONFIG_SECRET_KEYS = {'password', 'auth_token'}

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@event.listens_for(User, 'before_insert')
@event.listens_for(User, 'before_update')
def _validate_client_role(mapper, connection, user):
    # Checked at flush time (not via @validates) so the outcome doesn't
    # depend on the order role/client_id were passed to the constructor.
    if user.role == 'client' and user.client_id is None:
        raise ValueError("role 'client' requires client_id to be set")

def _require_client_or_fund(mapper, connection, instance):
    # A row must be scoped to at least one of a client's own portfolio or a
    # fund/strategy's own model portfolio (shared across every client
    # invested in it). Both may be set together (e.g. one client's holding
    # attributed to a specific fund) -- _scoped() in report_content.py
    # already narrows by fund_id within a client when both are present.
    label = instance.__class__.__name__
    if instance.client_id is None and instance.fund_id is None:
        raise ValueError(f"{label} requires either client_id or fund_id to be set")

class FundData(Base):
    __tablename__ = 'fund_data'
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    asset_class = Column(String(50))
    ticker = Column(String(20), nullable=True)
    inception_date = Column(Date, nullable=True)
    description = Column(Text, nullable=True)
    investment_universe = Column(String(150), nullable=True)

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "asset_class": self.asset_class,
            "ticker": self.ticker,
            "inception_date": self.inception_date.isoformat() if self.inception_date else None,
            "description": self.description,
            "investment_universe": self.investment_universe,
        }

class Client(Base):
    __tablename__ = 'clients'
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    contact_email = Column(String(100))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def serialize(self):
        return {"id": self.id, "name": self.name, "contact_email": self.contact_email}

class Contact(Base):
    __tablename__ = 'contacts'
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    name = Column(String(150), nullable=False)
    email = Column(String(100), nullable=True)
    title = Column(String(100), nullable=True)
    phone = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "name": self.name,
            "email": self.email,
            "title": self.title,
            "phone": self.phone,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

class Report(Base):
    __tablename__ = 'reports'
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=True)
    fund_id = Column(Integer, ForeignKey('fund_data.id'), nullable=True)
    template_id = Column(Integer, ForeignKey('report_templates.id'), nullable=True)
    team = Column(String(60), nullable=True)
    report_type = Column(String(30), nullable=True)
    status = Column(String(20), nullable=False, default='draft')
    file_path = Column(String(255))
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "title": self.title,
            "client_id": self.client_id,
            "fund_id": self.fund_id,
            "template_id": self.template_id,
            "team": self.team,
            "report_type": self.report_type,
            "status": self.status,
            "file_path": self.file_path,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

event.listens_for(Report, 'before_insert')(_require_client_or_fund)
event.listens_for(Report, 'before_update')(_require_client_or_fund)

class ReportTransition(Base):
    __tablename__ = 'report_transitions'
    id = Column(Integer, primary_key=True)
    report_id = Column(Integer, ForeignKey('reports.id'), nullable=False)
    from_status = Column(String(20))
    to_status = Column(String(20), nullable=False)
    actor_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "report_id": self.report_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "actor_id": self.actor_id,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

class DataSource(Base):
    __tablename__ = 'data_sources'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    type = Column(String(20), nullable=False)  # 'snowflake' | 'api'
    config = Column(Text, nullable=False)  # JSON string
    last_synced_at = Column(DateTime, nullable=True)
    last_sync_status = Column(String(20), nullable=True)  # 'success' | 'error'
    last_sync_message = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def config_dict(self):
        return json.loads(self.config) if self.config else {}

    def serialize(self):
        redacted_config = {
            key: value for key, value in self.config_dict().items()
            if key not in CONFIG_SECRET_KEYS
        }
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "config": redacted_config,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "last_sync_status": self.last_sync_status,
            "last_sync_message": self.last_sync_message,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

class ReportTemplate(Base):
    __tablename__ = 'report_templates'
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    components = Column(Text, nullable=False)  # JSON list, order = document order
    disclosure_ids = Column(Text, nullable=True)  # JSON list of Disclosure ids, appended as trailing text blocks
    header_config = Column(Text, nullable=True)  # JSON: {title, subtitle} shown on every rendered page
    footer_config = Column(Text, nullable=True)  # JSON: {text} shown on every rendered page, plus page numbers
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def components_list(self):
        return json.loads(self.components) if self.components else []

    def disclosure_ids_list(self):
        return json.loads(self.disclosure_ids) if self.disclosure_ids else []

    def header_config_dict(self):
        return json.loads(self.header_config) if self.header_config else {}

    def footer_config_dict(self):
        return json.loads(self.footer_config) if self.footer_config else {}

    def serialize(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "components": self.components_list(),
            "disclosure_ids": self.disclosure_ids_list(),
            "header_config": self.header_config_dict(),
            "footer_config": self.footer_config_dict(),
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class Holding(Base):
    __tablename__ = 'holdings'
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=True)
    fund_id = Column(Integer, ForeignKey('fund_data.id'), nullable=True)
    as_of_date = Column(Date, nullable=False)
    security_id = Column(String(50), nullable=False)
    security_name = Column(String(200))
    asset_class = Column(String(50))
    quantity = Column(Numeric(18, 4))
    market_value = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(3), default='USD')
    weight_pct = Column(Numeric(7, 4), nullable=True)
    source_id = Column(Integer, ForeignKey('data_sources.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "fund_id": self.fund_id,
            "as_of_date": self.as_of_date.isoformat() if self.as_of_date else None,
            "security_id": self.security_id,
            "security_name": self.security_name,
            "asset_class": self.asset_class,
            "quantity": float(self.quantity) if self.quantity is not None else None,
            "market_value": float(self.market_value) if self.market_value is not None else None,
            "currency": self.currency,
            "weight_pct": float(self.weight_pct) if self.weight_pct is not None else None,
        }

event.listens_for(Holding, 'before_insert')(_require_client_or_fund)
event.listens_for(Holding, 'before_update')(_require_client_or_fund)

class PerformanceSnapshot(Base):
    __tablename__ = 'performance_snapshots'
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=True)
    fund_id = Column(Integer, ForeignKey('fund_data.id'), nullable=True)
    as_of_date = Column(Date, nullable=False)
    period_type = Column(String(10), nullable=False)  # MTD/QTD/YTD/1Y/ITD
    return_pct = Column(Numeric(9, 4), nullable=False)
    benchmark_return_pct = Column(Numeric(9, 4), nullable=True)
    source_id = Column(Integer, ForeignKey('data_sources.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "client_id": self.client_id,
            "fund_id": self.fund_id,
            "as_of_date": self.as_of_date.isoformat() if self.as_of_date else None,
            "period_type": self.period_type,
            "return_pct": float(self.return_pct) if self.return_pct is not None else None,
            "benchmark_return_pct": float(self.benchmark_return_pct) if self.benchmark_return_pct is not None else None,
        }

event.listens_for(PerformanceSnapshot, 'before_insert')(_require_client_or_fund)
event.listens_for(PerformanceSnapshot, 'before_update')(_require_client_or_fund)

class DistributionLink(Base):
    __tablename__ = 'distribution_links'
    id = Column(Integer, primary_key=True)
    report_id = Column(Integer, ForeignKey('reports.id'), nullable=False)
    token = Column(String(64), unique=True, nullable=False)
    contact_id = Column(Integer, ForeignKey('contacts.id'), nullable=True)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)

    def serialize(self):
        return {
            "id": self.id,
            "report_id": self.report_id,
            "token": self.token,
            "contact_id": self.contact_id,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
        }

class Disclosure(Base):
    __tablename__ = 'disclosures'
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    category = Column(String(60), nullable=True)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    def serialize(self):
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "category": self.category,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

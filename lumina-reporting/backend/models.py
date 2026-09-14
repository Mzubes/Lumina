import datetime

from sqlalchemy import event
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from werkzeug.security import check_password_hash, generate_password_hash

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

class FundData(Base):
    __tablename__ = 'fund_data'
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    asset_class = Column(String(50))

    def serialize(self):
        return {"id": self.id, "name": self.name, "asset_class": self.asset_class}

class Client(Base):
    __tablename__ = 'clients'
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    contact_email = Column(String(100))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def serialize(self):
        return {"id": self.id, "name": self.name, "contact_email": self.contact_email}

class Report(Base):
    __tablename__ = 'reports'
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    fund_id = Column(Integer, ForeignKey('fund_data.id'), nullable=True)
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
            "status": self.status,
            "file_path": self.file_path,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

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

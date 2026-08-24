from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String
from werkzeug.security import check_password_hash, generate_password_hash

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class FundData(Base):
    __tablename__ = 'fund_data'
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    asset_class = Column(String(50))

    def serialize(self):
        return {"id": self.id, "name": self.name, "asset_class": self.asset_class}

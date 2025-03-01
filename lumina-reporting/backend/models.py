from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Binary
from cryptography.fernet import Fernet
import os

Base = declarative_base()
# Initialize Fernet with the encryption key from environment/config
fernet = Fernet(os.environ.get("ENCRYPTION_KEY", "default_key").encode())

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(Binary, nullable=False)
    role = Column(String(20), nullable=False)

    def set_password(self, password):
        self.password = fernet.encrypt(password.encode())

    def check_password(self, password):
        return fernet.decrypt(self.password).decode() == password

class FundData(Base):
    __tablename__ = 'fund_data'
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    asset_class = Column(String(50))

    def serialize(self):
        return {"id": self.id, "name": self.name, "asset_class": self.asset_class}

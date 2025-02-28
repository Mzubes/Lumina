import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'super_secure_key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://user:password@localhost/lumina'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECURITY_PASSWORD_SALT = os.environ.get('SECURITY_PASSWORD_SALT') or 'random_salt'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt_super_secret'
    PERMANENT_SESSION_LIFETIME = 900  # Session timeout in seconds (15 mins)
    ENABLE_MFA = True  # Toggle MFA

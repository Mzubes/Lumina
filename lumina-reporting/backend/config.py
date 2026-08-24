import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'development-only-secret')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///lumina.db').replace(
        'postgres://', 'postgresql+psycopg://', 1
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'development-only-jwt-secret')
    PERMANENT_SESSION_LIFETIME = 900  # 15 minutes
    CORS_ORIGINS = [origin.strip() for origin in os.environ.get(
        'CORS_ORIGINS', 'http://localhost:3000'
    ).split(',') if origin.strip()]

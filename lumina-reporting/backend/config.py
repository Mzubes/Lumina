import os

def _normalize_database_uri(raw_url):
    # Different Postgres hosts hand out different URL prefixes -- Render's
    # own database uses the old Heroku-style 'postgres://', while Neon and
    # most others use 'postgresql://'. Neither names a driver, so without
    # this SQLAlchemy defaults to psycopg2, which isn't installed (only
    # psycopg3, via the 'psycopg[binary]' package, is in requirements.txt).
    for prefix in ('postgres://', 'postgresql://'):
        if raw_url.startswith(prefix) and not raw_url.startswith('postgresql+'):
            return 'postgresql+psycopg://' + raw_url[len(prefix):]
    return raw_url

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'development-only-secret')
    SQLALCHEMY_DATABASE_URI = _normalize_database_uri(
        os.environ.get('DATABASE_URL', 'sqlite:///lumina.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'development-only-jwt-secret')
    PERMANENT_SESSION_LIFETIME = 900  # 15 minutes
    CORS_ORIGINS = [origin.strip() for origin in os.environ.get(
        'CORS_ORIGINS', 'http://localhost:3000'
    ).split(',') if origin.strip()]

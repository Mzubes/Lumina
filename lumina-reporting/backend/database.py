from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

engine = None
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False))

def configure_database(database_uri):
    global engine
    if engine is not None:
        engine.dispose()
    engine = create_engine(database_uri)
    db_session.remove()
    db_session.configure(bind=engine)

def init_db():
    import models  # Import all models here
    models.Base.metadata.create_all(bind=engine)

def shutdown_session(exception=None):
    db_session.remove()

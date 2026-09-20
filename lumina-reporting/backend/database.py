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
    import schema_v2

    models.Base.metadata.create_all(bind=engine)
    # v2 has its own declarative Base on purpose, so the two schemas can
    # stand side by side through the cutover. That also means it is invisible
    # to models.Base.metadata and has to be created explicitly -- without
    # this, every v2 table is a class with no table behind it, which is
    # exactly what it was until the template API needed to persist.
    schema_v2.metadata.create_all(bind=engine)

def shutdown_session(exception=None):
    db_session.remove()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from configs.config import get_settings
from contextlib import contextmanager

settings = get_settings()

DATABASE_URL = settings.database.postgres_connection_string.get_secret_value()
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get the database session
@contextmanager
def get_db_context():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
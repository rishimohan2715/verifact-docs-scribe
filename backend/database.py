import os
import logging
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

# Create data directory if it doesn't exist
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STORAGE_DIR = os.path.join(BASE_DIR, "storage", "audio")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(STORAGE_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "verifact_local.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}  # Needed for SQLite
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def ensure_schema_current():
    """
    Additive schema migration for the local SQLite database.

    Base.metadata.create_all() only creates tables that are missing entirely — it
    never adds a new column to a table that already exists. So whenever a model
    gains a column, every INSERT against an older database file fails with
    "table X has no column named Y". Backfill any missing nullable columns here.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue

            present = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in present:
                    continue
                if not column.nullable and column.default is None:
                    logger.warning(
                        f"Cannot auto-add required column {table.name}.{column.name} "
                        "to the existing database; a manual migration is needed."
                    )
                    continue

                col_type = column.type.compile(engine.dialect)
                conn.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}"))
                logger.info(f"Added missing column {table.name}.{column.name} ({col_type})")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


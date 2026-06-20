"""SQLAlchemy engine / session setup.

Designed to work with SQLite for local/dev and a server database (PostgreSQL,
MySQL, …) in production — just point DATABASE_URL at it. Connection pooling and
pre-ping are enabled so dropped connections recover automatically.

SQLAlchemy 1.3 compatible.
"""
import logging

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import settings

log = logging.getLogger("ultimate_dashboard.db")

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# SQLite needs check_same_thread off for the threaded server; networked DBs get
# a real connection pool that recycles and pre-pings stale connections.
if _is_sqlite:
    engine_kwargs = {"connect_args": {"check_same_thread": False}}
else:
    engine_kwargs = {
        "pool_pre_ping": True,   # drop dead connections instead of erroring
        "pool_recycle": 1800,    # recycle connections every 30 min
        "pool_size": 10,
        "max_overflow": 20,
    }

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        """Tune SQLite for a concurrent web server on every new connection.

        WAL lets readers and a writer work at once (no more 'database is locked'
        under load); busy_timeout makes a writer wait briefly instead of erroring;
        synchronous=NORMAL is the safe/fast pairing with WAL.
        """
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.close()


def get_db():
    """FastAPI dependency: yields a session, rolls back on error, always closes."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Columns added after the first release. For SQLite we add them in-place so an
# existing database keeps working without a full migration tool. For other DBs,
# use a real migration (see docs/HANDOVER.md).
_EXPECTED_COLUMNS = {
    "dashboards": {
        "status": "VARCHAR(20) NOT NULL DEFAULT 'pending'",
        "submitted_by": "VARCHAR(64)",
    },
    "users": {
        "theme_preference": "VARCHAR(10) NOT NULL DEFAULT 'light'",
        "avatar_url": "VARCHAR(500)",
    },
}


def _apply_lightweight_migrations():
    """Add any missing columns (SQLite only). Never crashes startup."""
    if not _is_sqlite:
        return
    try:
        insp = inspect(engine)
        existing_tables = set(insp.get_table_names())
        with engine.begin() as conn:
            for table, columns in _EXPECTED_COLUMNS.items():
                if table not in existing_tables:
                    continue  # create_all builds it fresh with all columns
                have = {c["name"] for c in insp.get_columns(table)}
                for col, ddl in columns.items():
                    if col not in have:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
                        log.info("Added column %s.%s", table, col)
    except Exception as exc:  # noqa: BLE001 - migration must not block startup
        log.warning("Lightweight migration skipped due to error: %s", exc)


def init_db():
    """Create all tables and apply small migrations. Models must be importable."""
    import app.models  # noqa: F401  (ensures models are registered on Base)

    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations()

from sqlalchemy import create_engine, String, Text, Integer, DateTime, UniqueConstraint, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from datetime import datetime, timezone
from .settings import DB_URL

engine = create_engine(
    DB_URL,
    future=True,
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {},
)


@event.listens_for(engine, "connect")
def _configure_sqlite_connection(dbapi_connection, connection_record):
    """Make the shared metadata cache friendlier for multiple UI users.

    SQLite is still only a local cache, but WAL allows readers to keep browsing
    while a background sync writes new rows. busy_timeout avoids short-lived
    writer/read conflicts surfacing as errors during heavy syncs.
    """
    if not DB_URL.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.execute("PRAGMA temp_store=MEMORY")
    finally:
        cursor.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

class Base(DeclarativeBase):
    pass

class CachedObject(Base):
    __tablename__ = "cached_objects"
    __table_args__ = (UniqueConstraint("environment", "object_type", "object_name", name="uq_cached_object"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    environment: Mapped[str] = mapped_column(String(64), index=True)
    object_type: Mapped[str] = mapped_column(String(64), index=True)
    object_name: Mapped[str] = mapped_column(String(512), index=True)
    object_hash: Mapped[str] = mapped_column(String(64), index=True)
    json_data: Mapped[str] = mapped_column(Text)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

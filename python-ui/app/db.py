from sqlalchemy import create_engine, String, Text, Integer, DateTime, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from datetime import datetime, timezone
from .settings import DB_URL

engine = create_engine(DB_URL, future=True)
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

"""Optional SQLAlchemy persistence for anonymous generated plans."""
from __future__ import annotations
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

try:
    from sqlalchemy import DateTime, Float, Integer, String, create_engine, JSON
    from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
    SQLALCHEMY_AVAILABLE = True
except Exception:  # pragma: no cover
    SQLALCHEMY_AVAILABLE = False


if SQLALCHEMY_AVAILABLE:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./beforma_generated_plans.db")
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    class Base(DeclarativeBase):
        pass

    class GeneratedPlan(Base):
        __tablename__ = "generated_plans"
        id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
        request_id: Mapped[str] = mapped_column(String(64), index=True)
        age: Mapped[int | None] = mapped_column(Integer, nullable=True)
        gender: Mapped[str | None] = mapped_column(String(32), nullable=True)
        height: Mapped[float | None] = mapped_column(Float, nullable=True)
        weight: Mapped[float | None] = mapped_column(Float, nullable=True)
        fitness_goal: Mapped[str | None] = mapped_column(String(64), nullable=True)
        activity_level: Mapped[str | None] = mapped_column(String(64), nullable=True)
        experience_level: Mapped[str | None] = mapped_column(String(64), nullable=True)
        workout_location: Mapped[str | None] = mapped_column(String(64), nullable=True)
        dietary_preference: Mapped[str | None] = mapped_column(String(64), nullable=True)
        selection_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
        bmi: Mapped[float | None] = mapped_column(Float, nullable=True)
        bmi_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
        daily_calorie_target: Mapped[float | None] = mapped_column(Float, nullable=True)
        macros_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
        diet_plan_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
        workout_plan_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
        food_selection_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
        raw_request_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
        raw_response_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
        created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def init_db() -> None:
        Base.metadata.create_all(bind=engine)

    @contextmanager
    def db_session() -> Iterator:
        db = SessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
else:
    class GeneratedPlan:  # type: ignore
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    def init_db() -> None:
        return None

    class _DummySession:
        def add(self, _obj): return None
        def commit(self): return None
        def rollback(self): return None
        def close(self): return None

    @contextmanager
    def db_session() -> Iterator:
        yield _DummySession()

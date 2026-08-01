from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
# expire_on_commit=False: the default (True) marks every attribute on a
# committed object stale, so the next read re-queries the DB to refresh it.
# The orchestrator commits after every stage (progress.emit) and then hands
# the same `job` object to 4 worker threads in the parallel generation batch —
# with the default, each thread's first read of job.stage_results/teaching_context
# after a commit would trigger a lazy-reload against the *same* Session
# concurrently, and SQLAlchemy Sessions are not safe for concurrent use from
# multiple threads. That's what caused the parallel-stage hang: not a crash,
# but multiple threads contending for one connection with no clean failure.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings


def create_db_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().effective_database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


def create_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    bind = engine or create_db_engine()
    return sessionmaker(bind=bind, autoflush=False, autocommit=False, future=True)


SessionLocal = create_session_factory()


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


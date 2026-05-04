from collections.abc import Sequence
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base


ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    def __init__(self, session: Session, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        self.session.flush()
        return instance

    def get(self, primary_key: int) -> ModelT | None:
        return self.session.get(self.model, primary_key)

    def list(self, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        statement = select(self.model).offset(offset).limit(limit)
        return self.session.execute(statement).scalars().all()


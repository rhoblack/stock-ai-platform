"""Repository for v0.8 Phase B User rows."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.repositories.base import BaseRepository
from app.db.base import utc_now
from app.db.models import User


class UserRepository(BaseRepository[User]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, User)

    def create(
        self,
        *,
        username: str,
        password_hash: str,
        is_admin: bool = False,
        is_active: bool = True,
    ) -> User:
        """Insert a new user. Caller is responsible for hashing the password.

        ``password_hash`` MUST already be a scrypt-hashed string produced by
        ``app.auth.security.PasswordHasher.hash_password``. Passing a plaintext
        password would persist plaintext -- this method does not validate the
        format because the hasher is the single producer.
        """
        return self.add(
            User(
                username=username,
                password_hash=password_hash,
                is_admin=is_admin,
                is_active=is_active,
            ),
        )

    def get_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        statement = select(User).where(User.username == username)
        return self.session.execute(statement).scalar_one_or_none()

    def set_last_login(self, user: User) -> User:
        """Update ``last_login_at`` and ``updated_at`` to the current UTC time."""
        now = utc_now()
        user.last_login_at = now
        user.updated_at = now
        self.session.flush()
        return user

    def deactivate(self, user: User) -> User:
        user.is_active = False
        user.updated_at = utc_now()
        self.session.flush()
        return user

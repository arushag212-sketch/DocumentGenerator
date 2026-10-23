"""Scoped repository enforcing strict club_id isolation on all database queries."""

from __future__ import annotations

from typing import Any, Generic, Optional, Type, TypeVar
from sqlalchemy import select
from sqlalchemy.orm import Session

T = TypeVar("T")


class ScopedRepository(Generic[T]):
    """Repository enforcing that all queries and writes require and check club_id."""

    def __init__(self, db: Session, model_cls: Type[T], club_id: str, *, include_deleted: bool = False):
        if not club_id:
            raise ValueError("club_id is required for ScopedRepository to prevent cross-club leakage")
        self.db = db
        self.model_cls = model_cls
        self.club_id = club_id
        # Documents in the Trash are hidden from every query; the Trash and verify code opt in.
        self.include_deleted = include_deleted

    def _select(self, *columns: Any):
        stmt = select(*columns) if columns else select(self.model_cls)
        return stmt.execution_options(include_deleted=True) if self.include_deleted else stmt

    def get(self, entity_id: str) -> Optional[T]:
        """Fetch an entity strictly scoped to the repository's club_id."""
        stmt = self._select().where(
            self.model_cls.id == entity_id,  # type: ignore[attr-defined]
            self.model_cls.club_id == self.club_id,  # type: ignore[attr-defined]
        )
        return self.db.scalars(stmt).first()

    def find_first(self, *filters: Any) -> Optional[T]:
        """Find the first entity matching the given filters, strictly scoped to club_id."""
        stmt = self._select().where(
            self.model_cls.club_id == self.club_id,  # type: ignore[attr-defined]
            *filters,
        )
        return self.db.scalars(stmt).first()

    def list(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[list[Any]] = None,
        order_by: Optional[Any] = None,
    ) -> list[T]:
        """List entities strictly scoped to the repository's club_id."""
        stmt = self._select().where(
            self.model_cls.club_id == self.club_id  # type: ignore[attr-defined]
        )
        if filters:
            for f in filters:
                stmt = stmt.where(f)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        else:
            if hasattr(self.model_cls, "created_at"):
                stmt = stmt.order_by(self.model_cls.created_at.desc())  # type: ignore[attr-defined]
        stmt = stmt.offset(skip).limit(limit)
        return list(self.db.scalars(stmt).all())

    def all(self, *filters: Any) -> list[T]:
        """Return all matching entities scoped to this club_id."""
        stmt = self._select().where(
            self.model_cls.club_id == self.club_id,  # type: ignore[attr-defined]
            *filters,
        )
        if hasattr(self.model_cls, "created_at"):
            stmt = stmt.order_by(self.model_cls.created_at.desc())  # type: ignore[attr-defined]
        return list(self.db.scalars(stmt).all())

    def count(self, *filters: Any) -> int:
        """Count entities strictly scoped to this club_id."""
        from sqlalchemy import func
        stmt = self._select(func.count(self.model_cls.id)).where(  # type: ignore[attr-defined]
            self.model_cls.club_id == self.club_id,  # type: ignore[attr-defined]
            *filters,
        )
        return self.db.scalar(stmt) or 0

    def create(self, *, commit: bool = False, **kwargs: Any) -> T:
        """Create a new entity, guaranteeing club_id is set to this repository's club_id."""
        kwargs["club_id"] = self.club_id
        entity = self.model_cls(**kwargs)
        self.db.add(entity)
        # Repositories participate in the caller's transaction by default.  A
        # commit here can persist half of a request before a later validation or
        # render step fails (and makes audit rows impossible to roll back with
        # the operation they describe).  Callers that explicitly need an early
        # commit can opt in, but normal request code should commit once at the
        # end of the unit of work.
        self.db.flush()
        if commit:
            self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, entity_id: str, *, commit: bool = False, **kwargs: Any) -> Optional[T]:
        """Update an entity only if it belongs to this club_id."""
        entity = self.get(entity_id)
        if not entity:
            return None
        # Disallow tampering with club_id
        kwargs.pop("club_id", None)
        for key, value in kwargs.items():
            if hasattr(entity, key):
                setattr(entity, key, value)
        self.db.flush()
        if commit:
            self.db.commit()
        self.db.refresh(entity)
        return entity

    def delete(self, entity_id: str, *, commit: bool = False) -> bool:
        """Delete an entity only if it belongs to this club_id."""
        entity = self.get(entity_id)
        if not entity:
            return False
        self.db.delete(entity)
        self.db.flush()
        if commit:
            self.db.commit()
        return True


def get_scoped_repository(db: Session, model_cls: Type[T], club_id: str) -> ScopedRepository[T]:
    """Factory for ScopedRepository."""
    return ScopedRepository(db, model_cls, club_id)

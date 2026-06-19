from datetime import UTC, datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.base import BaseModel as DBBaseModel

ModelType = TypeVar("ModelType", bound=DBBaseModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class PaginatedResult:
    def __init__(self, data: list, total: int, page: int, page_size: int):
        self.data = data
        self.total = total
        self.page = page
        self.page_size = page_size
        self.total_pages = (total + page_size - 1) // page_size


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType], db: Session):
        self.model = model
        self.db = db

    def get_by_id(self, id: UUID) -> ModelType | None:
        return (
            self.db.query(self.model)
            .filter(
                self.model.id == id,
                self.model.deleted_at.is_(None),
            )
            .first()
        )

    def get_by_id_or_raise(self, id: UUID) -> ModelType:
        obj = self.get_by_id(id)
        if not obj:
            raise ValueError(f"{self.model.__name__} with id {id} not found")
        return obj

    def get_all_paginated(
        self,
        page: int = 1,
        page_size: int = 20,
        hospital_id: UUID | None = None,
        filters: list = None,
    ) -> PaginatedResult:
        """
        hospital_id is now an OPTIONAL filter, not a mandatory tenancy
        boundary. Under the marketplace model, hospital_id is nullable
        (or absent entirely) on most models — it's a historical/
        affiliation field, not an isolation boundary. Pass it only when
        you specifically want to scope results to one hospital (e.g.
        admin reviewing appointments at a specific hospital for
        reporting). If the model has no hospital_id column at all
        (User, Patient), passing hospital_id will raise AttributeError —
        callers must not pass it for those repos.
        """
        query = self.db.query(self.model).filter(
            self.model.deleted_at.is_(None),
        )

        if hospital_id is not None:
            if not hasattr(self.model, "hospital_id"):
                raise ValueError(
                    f"{self.model.__name__} has no hospital_id column — "
                    "cannot filter by hospital_id"
                )
            query = query.filter(self.model.hospital_id == hospital_id)

        if filters:
            for f in filters:
                query = query.filter(f)

        total = query.count()
        data = (
            query
            .order_by(self.model.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return PaginatedResult(data=data, total=total, page=page, page_size=page_size)

    def create(self, data: dict) -> ModelType:
        obj = self.model(**data)
        self.db.add(obj)
        self.db.flush()   # flush to get ID, service controls commit
        self.db.refresh(obj)
        return obj

    def update(self, obj: ModelType, data: dict) -> ModelType:
        for key, value in data.items():
            if hasattr(obj, key) and value is not None:
                setattr(obj, key, value)
        self.db.flush()
        self.db.refresh(obj)
        return obj

    def soft_delete(self, obj: ModelType) -> ModelType:
        obj.deleted_at = datetime.now(UTC)
        self.db.flush()
        return obj
    
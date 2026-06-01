from typing import Generic, TypeVar, Type, Optional, List
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from pydantic import BaseModel
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
    def __init__(self, model: Type[ModelType], db: Session):
        self.model = model
        self.db = db

    def get_by_id(self, id: UUID) -> Optional[ModelType]:
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
        hospital_id: UUID,
        page: int = 1,
        page_size: int = 20,
        filters: list = None,
    ) -> PaginatedResult:
        query = self.db.query(self.model).filter(
            self.model.hospital_id == hospital_id,
            self.model.deleted_at.is_(None),
        )
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
        obj.deleted_at = datetime.now(timezone.utc)
        self.db.flush()
        return obj
from typing import Generic, TypeVar

from pydantic import BaseModel, field_validator

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20

    @field_validator("page")
    @classmethod
    def page_must_be_positive(cls, v):
        if v < 1:
            raise ValueError("Page must be 1 or greater")
        return v

    @field_validator("page_size")
    @classmethod
    def page_size_must_be_in_range(cls, v):
        if v < 1:
            raise ValueError("Page size must be at least 1")
        if v > 100:
            raise ValueError("Page size cannot exceed 100")
        return v


class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    model_config = {"from_attributes": True}

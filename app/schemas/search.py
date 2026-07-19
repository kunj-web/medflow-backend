from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class SearchResult(BaseModel):
    id: UUID
    kind: str
    title: str
    subtitle: str
    meta: str
    href: str


class SearchResponse(BaseModel):
    data: list[SearchResult]

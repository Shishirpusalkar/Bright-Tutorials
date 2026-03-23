from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .user import User


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Base Schema
class ItemBase(SQLModel):
    title: str
    description: str | None = None


class Item(ItemBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    title: str
    description: str | None = None
    created_at: datetime = Field(
        default_factory=utc_now,
        nullable=False,
        sa_type=DateTime(timezone=True),
    )
    owner_id: UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )
    owner: "User" = Relationship(back_populates="items")


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(ItemBase):
    title: str | None = None  # type: ignore
    description: str | None = None  # type: ignore


class ItemPublic(ItemBase):
    id: UUID
    owner_id: UUID


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int

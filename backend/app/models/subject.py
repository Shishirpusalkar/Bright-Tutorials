from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .chapter import Chapter
    from .test import Test


class Subject(SQLModel, table=True):
    __tablename__ = "subjects"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(unique=True, index=True)

    # Relationships
    chapters: list["Chapter"] = Relationship(back_populates="subject")
    tests: list["Test"] = Relationship(back_populates="subject")

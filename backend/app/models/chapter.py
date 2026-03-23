from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel


if TYPE_CHECKING:
    from .question import Question
    from .subject import Subject


class Chapter(SQLModel, table=True):
    __tablename__ = "chapters"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    subject_id: UUID = Field(foreign_key="subjects.id")

    # Relationships
    subject: "Subject" = Relationship(back_populates="chapters")
    questions: list["Question"] = Relationship(back_populates="chapter")

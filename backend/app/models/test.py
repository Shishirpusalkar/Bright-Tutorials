from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .user import User
    from .subject import Subject
    from .question import Question
    from .attempt import Attempt


class Test(SQLModel, table=True):
    __tablename__ = "tests"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    title: str
    description: str | None = None
    instructions: str | None = None

    duration_minutes: int
    total_marks: int = 0

    question_paper_url: str | None = None  # PDF URL
    standard: str | None = None  # e.g. 11th, 12th
    category: str | None = None  # e.g. JEE, NEET, JEE Advanced

    created_by: UUID = Field(foreign_key="user.id")
    subject_id: UUID | None = Field(default=None, foreign_key="subjects.id")

    is_published: bool = False
    scheduled_at: datetime | None = None

    is_symmetrical: bool | None = Field(default=None)
    symmetry_message: str | None = Field(default=None)

    positive_marks: int = Field(default=4)
    negative_marks: float = Field(default=-1.0)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationships
    creator: "User" = Relationship(back_populates="tests")
    subject: Optional["Subject"] = Relationship(back_populates="tests")
    questions: list["Question"] = Relationship(
        back_populates="test", cascade_delete=True
    )
    attempts: list["Attempt"] = Relationship(back_populates="test", cascade_delete=True)


class TestPublic(SQLModel):
    id: UUID
    title: str
    description: str | None = None
    instructions: str | None = None
    duration_minutes: int
    total_marks: int
    question_paper_url: str | None = None
    standard: str | None = None
    category: str | None = None
    is_published: bool
    scheduled_at: datetime | None = None
    positive_marks: int
    negative_marks: float
    created_at: datetime
    questions: list["QuestionPublic"] = []

    # Analytics
    submission_count: int = 0
    average_score: float = 0.0
    is_symmetrical: bool | None = None
    symmetry_message: str | None = None


from .question import QuestionPublic  # type: ignore

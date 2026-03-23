from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .attempt_answer import AttemptAnswer
    from .tab_activity import TabActivity
    from .test import Test
    from .user import User


class AttemptStatus(str, Enum):
    ONGOING = "ongoing"
    SUBMITTED = "submitted"


class Attempt(SQLModel, table=True):
    __tablename__ = "attempts"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    student_id: UUID = Field(foreign_key="user.id")
    test_id: UUID = Field(foreign_key="tests.id")

    score: int = 0
    status: AttemptStatus = Field(default=AttemptStatus.ONGOING)

    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_at: datetime | None = None

    tab_switch_count: int = 0
    ai_analysis: str | None = None
    section_results: dict | None = Field(default=None, sa_column=Column(JSON))

    # Relationships
    student: "User" = Relationship(back_populates="attempts")
    test: "Test" = Relationship(back_populates="attempts")
    tab_activities: list["TabActivity"] = Relationship(
        back_populates="attempt", cascade_delete=True
    )
    answers: list["AttemptAnswer"] = Relationship(
        back_populates="attempt", cascade_delete=True
    )


from .attempt_answer import AttemptAnswerPublic


class AttemptPublic(SQLModel):
    id: UUID
    student_id: UUID
    test_id: UUID
    score: int
    status: AttemptStatus
    started_at: datetime
    submitted_at: datetime | None = None
    tab_switch_count: int
    ai_analysis: str | None = None
    section_results: dict | None = None
    answers: list[AttemptAnswerPublic] = []

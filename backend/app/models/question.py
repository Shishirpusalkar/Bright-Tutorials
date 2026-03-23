from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, JSON
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .attempt_answer import AttemptAnswer
    from .chapter import Chapter
    from .test import Test


class Question(SQLModel, table=True):
    __tablename__ = "questions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    test_id: UUID = Field(foreign_key="tests.id")
    chapter_id: UUID | None = Field(default=None, foreign_key="chapters.id")

    question_text: str
    image_url: str | None = None

    # Options (nullable for numeric questions)
    option_a: str | None = None
    option_b: str | None = None
    option_c: str | None = None
    option_d: str | None = None

    # Structured options for multiple correct/matching questions
    options: dict | None = Field(default=None, sa_column=Column(JSON))

    correct_option: str | None = None  # A/B/C/D or Numeric Answer
    marks: float = 1.0
    negative_marks: float = 0.0

    # New Fields for Advanced Features
    subject: str | None = None  # Physics, Chemistry, Maths
    standard: str | None = None  # 11th, 12th
    category: str | None = None  # JEE, NEET
    section: str | None = None  # Section A, Section B
    question_type: str = "MCQ"  # MCQ, NUMERIC, SCQ, etc.
    question_number: int | None = None
    solution_text: str | None = None
    solution_bbox: dict | None = Field(default=None, sa_column=Column(JSON))

    # For Smart Deduplication
    content_hash: str | None = Field(default=None, index=True)

    # Omega Go - Advanced Metadata
    organic_metadata: dict | None = Field(default=None, sa_column=Column(JSON))
    diagram_description: str | None = None
    has_visual: bool = Field(default=False)
    visual_tag: str | None = None
    page_number: int | None = None
    visual_bbox: dict | None = Field(default=None, sa_column=Column(JSON))

    # Relationships
    test: Optional["Test"] = Relationship(back_populates="questions")
    chapter: Optional["Chapter"] = Relationship(back_populates="questions")
    attempt_answers: list["AttemptAnswer"] = Relationship(
        back_populates="question", cascade_delete=True
    )


class QuestionPublic(SQLModel):
    id: UUID
    question_text: str
    option_a: str | None = None
    option_b: str | None = None
    option_c: str | None = None
    option_d: str | None = None
    options: dict | None = None
    marks: float
    negative_marks: float
    subject: str | None = None
    standard: str | None = None
    category: str | None = None
    section: str | None = None
    question_type: str = "MCQ"
    question_number: int | None = None
    solution_text: str | None = None
    solution_bbox: dict | None = None
    image_url: str | None = None
    content_hash: str | None = None
    organic_metadata: dict | None = None
    diagram_description: str | None = None
    has_visual: bool = False
    visual_tag: str | None = None
    page_number: int | None = None
    visual_bbox: dict | None = None

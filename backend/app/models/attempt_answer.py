from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .attempt import Attempt
    from .question import Question


class AttemptAnswer(SQLModel, table=True):
    __tablename__ = "attempt_answers"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    attempt_id: UUID = Field(foreign_key="attempts.id")
    question_id: UUID = Field(foreign_key="questions.id")

    selected_option: str | None = None  # A, B, C, D
    answer_text: str | None = None  # For Numeric

    is_correct: bool = False
    marks_obtained: int = 0
    time_spent_seconds: int = 0

    # Relationships
    attempt: "Attempt" = Relationship(back_populates="answers")
    question: "Question" = Relationship(back_populates="attempt_answers")


class AttemptAnswerPublic(SQLModel):
    id: UUID
    question_id: UUID
    selected_option: str | None = None
    answer_text: str | None = None
    is_correct: bool
    marks_obtained: int
    time_spent_seconds: int

    # Optional nested data for analysis
    question_text: str | None = None
    solution_text: str | None = None
    correct_option: str | None = None
    correct_answer_text: str | None = None

    # Enrichment fields for detailed solutions
    marks: float | None = None
    organic_metadata: dict | None = None
    diagram_description: str | None = None
    has_visual: bool = False
    visual_tag: str | None = None
    question_type: str | None = None
    page_number: int | None = None
    visual_bbox: dict | None = None
    solution_bbox: dict | None = None
    image_url: str | None = None
    question_paper_url: str | None = None

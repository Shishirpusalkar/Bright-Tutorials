from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .attempt import Attempt


class TabActivity(SQLModel, table=True):
    __tablename__ = "tab_activities"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    attempt_id: UUID = Field(foreign_key="attempts.id")

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str  # "blur" or "focus"

    # Relationships
    attempt: "Attempt" = Relationship(back_populates="tab_activities")

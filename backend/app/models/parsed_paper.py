from uuid import UUID, uuid4
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, JSON


class ParsedPaperCache(SQLModel, table=True):
    __tablename__ = "parsed_paper_cache"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    pdf_hash: str = Field(index=True, unique=True)

    # Store the list of questions as JSON
    data: dict = Field(default_factory=dict, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

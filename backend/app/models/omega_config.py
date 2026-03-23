from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, JSON


class TestGenerationConfig(SQLModel, table=True):
    __tablename__ = "test_generation_configs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    test_id: UUID = Field(foreign_key="tests.id", index=True)
    pdf_hash: str | None = Field(default=None, index=True)

    # Store teacher's config (subjects, sections, marks, counts)
    config_data: dict[str, Any] = Field(default={}, sa_column=Column(JSON))

    # Store parsing stats (questions found, API usage, etc.)
    parsing_report: dict[str, Any] = Field(default={}, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.now)

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from pydantic import EmailStr
from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .item import Item
    from .test import Test
    from .attempt import Attempt


# Helpers
def utcnow():
    return datetime.now(timezone.utc)


# Enums
class UserRole(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


# Base
class UserBase(SQLModel):
    email: EmailStr = Field(index=True, unique=True, max_length=255)
    full_name: str | None = Field(default=None, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    role: UserRole = Field(default=UserRole.STUDENT)
    is_premium: bool = Field(default=False)
    standard: str | None = Field(
        default=None, max_length=50
    )  # e.g., 11th, 12th, Dropper
    stream: str | None = Field(
        default=None, max_length=50
    )  # e.g., engineering, medical
    grade: int | None = Field(default=None)  # 11 or 12
    is_paid: bool = Field(default=False)
    payment_status: str | None = Field(default=None, max_length=255)
    payment_id: str | None = Field(default=None, max_length=255)

    # Fee Management
    fee_override: float | None = Field(default=None)
    is_fee_exempt: bool = Field(default=False)
    premium_expiry: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )

    # Tracking
    last_active_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True))
    )
    current_path: str | None = Field(default=None, max_length=255)


# Database Model
class User(UserBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=utcnow,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    hashed_password: str
    # Relationships
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)
    tests: list["Test"] = Relationship(back_populates="creator", cascade_delete=True)
    attempts: list["Attempt"] = Relationship(
        back_populates="student", cascade_delete=True
    )


# Schemas
class UserCreate(SQLModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = None
    is_superuser: bool = False
    role: UserRole = UserRole.STUDENT
    standard: str | None = None
    stream: str | None = None


class UserUpdate(SQLModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    is_premium: Optional[bool] = None
    premium_expiry: Optional[datetime] = None


class UserPublic(SQLModel):
    id: UUID
    email: EmailStr
    full_name: Optional[str]
    role: UserRole
    is_superuser: bool
    is_premium: bool
    standard: str | None
    stream: str | None
    grade: int | None
    is_paid: bool
    payment_status: str | None
    payment_id: str | None
    fee_override: float | None
    is_fee_exempt: bool
    premium_expiry: datetime | None
    last_active_at: datetime | None
    current_path: str | None
    created_at: datetime


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    role: UserRole = UserRole.STUDENT
    standard: str = Field(..., max_length=50)
    stream: str = Field(..., max_length=50)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int

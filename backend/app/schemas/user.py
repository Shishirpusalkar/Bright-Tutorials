from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from app.models import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: UserRole


class UserLogin(BaseModel):
    username: EmailStr
    password: str


class UserRead(BaseModel):
    id: UUID
    email: EmailStr
    role: UserRole

    class Config:
        from_attributes = True
